/*
 * 004_web_features.sql
 *
 * 일반 웹 기능을 PostgreSQL에 저장하기 위한 마이그레이션입니다.
 *
 * 적용 대상:
 * - 기존 users 테이블 확장
 * - faqs
 * - questions
 * - question_comments
 * - notifications
 * - query_history
 * - audit_logs
 *
 * 세션, 잠금 해제 정보, Idempotency-Key, Agent 실행 상태는
 * PostgreSQL이 아닌 Redis에서 관리하므로 포함하지 않습니다.

 기존 법률 데이터 테이블은 건드리지 않음
 기존 saved_conversations → users 연결 유지
 기존 익명 사용자 데이터 보존
 회원·비회원 소유권을 DB에서도 검증
 비회원 데이터에만 만료일 적용
 비밀번호 원문 저장 방지
 질문 삭제 시 댓글 자동 삭제
 관리자 감사 기록 보존
 실행 중 오류가 발생하면 전체 롤백
 다시 실행할 때 테이블·컬럼 중복 오류 방지
 */

BEGIN;

SET LOCAL lock_timeout = '5s';


/* =========================================================
 * 1. 기존 users 테이블 확장
 * ========================================================= */

/*
 * 기존 users는 anonymous_key가 필수인 익명 사용자용 테이블입니다.
 * 실제 회원도 저장할 수 있도록 anonymous_key를 선택값으로 변경합니다.
 *
 * users.id는 saved_conversations.user_id가 참조하므로
 * users 테이블을 삭제하거나 다시 생성하지 않습니다.
 */
ALTER TABLE public.users
    ALTER COLUMN anonymous_key DROP NOT NULL;

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS email VARCHAR(254),
    ADD COLUMN IF NOT EXISTS password_hash TEXT,
    ADD COLUMN IF NOT EXISTS display_name VARCHAR(30),
    ADD COLUMN IF NOT EXISTS role VARCHAR(10) NOT NULL DEFAULT 'GUEST',
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;


/*
 * 이메일은 공백 없는 소문자로 저장합니다.
 */
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'users_email_normalized_check'
          AND conrelid = 'public.users'::regclass
    ) THEN
        ALTER TABLE public.users
            ADD CONSTRAINT users_email_normalized_check
            CHECK (
                email IS NULL
                OR (
                    email = LOWER(BTRIM(email))
                    AND email <> ''
                    AND email LIKE '%@%'
                )
            );
    END IF;
END
$$;


/*
 * 역할은 GUEST, USER, ADMIN만 허용합니다.
 */
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'users_role_check'
          AND conrelid = 'public.users'::regclass
    ) THEN
        ALTER TABLE public.users
            ADD CONSTRAINT users_role_check
            CHECK (role IN ('GUEST', 'USER', 'ADMIN'));
    END IF;
END
$$;


/*
 * 익명 사용자는 anonymous_key가 필요합니다.
 * 회원과 관리자는 이메일, 비밀번호 Hash, 표시 이름이 필요합니다.
 */
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'users_identity_check'
          AND conrelid = 'public.users'::regclass
    ) THEN
        ALTER TABLE public.users
            ADD CONSTRAINT users_identity_check
            CHECK (
                (
                    role = 'GUEST'
                    AND anonymous_key IS NOT NULL
                    AND BTRIM(anonymous_key) <> ''
                    AND email IS NULL
                    AND password_hash IS NULL
                )
                OR
                (
                    role IN ('USER', 'ADMIN')
                    AND email IS NOT NULL
                    AND password_hash IS NOT NULL
                    AND display_name IS NOT NULL
                    AND BTRIM(display_name) <> ''
                )
            );
    END IF;
END
$$;


/*
 * 이메일 대소문자 차이로 중복 회원이 생기지 않도록 합니다.
 */
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower
    ON public.users (LOWER(email))
    WHERE email IS NOT NULL;


/* =========================================================
 * 2. FAQ
 * ========================================================= */

CREATE TABLE IF NOT EXISTS public.faqs (
    id TEXT PRIMARY KEY
        DEFAULT ('faq-' || gen_random_uuid()::TEXT),

    category VARCHAR(20) NOT NULL
        CONSTRAINT faqs_category_check
        CHECK (category IN ('housing', 'labor', 'consumer')),

    question VARCHAR(500) NOT NULL,
    answer VARCHAR(5000) NOT NULL,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
    display_order INTEGER NOT NULL DEFAULT 999
        CONSTRAINT faqs_display_order_check
        CHECK (display_order >= 0),

    created_by BIGINT
        REFERENCES public.users(id)
        ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT faqs_question_not_blank_check
        CHECK (BTRIM(question) <> ''),

    CONSTRAINT faqs_answer_not_blank_check
        CHECK (BTRIM(answer) <> '')
);


/* =========================================================
 * 3. 공개·비밀 질문
 * ========================================================= */

CREATE TABLE IF NOT EXISTS public.questions (
    id TEXT PRIMARY KEY
        DEFAULT ('question-' || gen_random_uuid()::TEXT),

    user_id BIGINT
        REFERENCES public.users(id)
        ON DELETE CASCADE,

    guest_id VARCHAR(100),

    display_name VARCHAR(30) NOT NULL,

    category VARCHAR(20) NOT NULL
        CONSTRAINT questions_category_check
        CHECK (category IN ('housing', 'labor', 'consumer')),

    title VARCHAR(100) NOT NULL,
    content VARCHAR(2000) NOT NULL,

    /*
     * 현재 Backend API는 회원과 비회원 모두 질문 비밀번호를 받습니다.
     * 원문 비밀번호가 아니라 Hash만 저장해야 합니다.
     */
    password_hash TEXT NOT NULL,

    visibility VARCHAR(10) NOT NULL DEFAULT 'PRIVATE'
        CONSTRAINT questions_visibility_check
        CHECK (visibility IN ('PUBLIC', 'PRIVATE')),

    status VARCHAR(10) NOT NULL DEFAULT 'PENDING'
        CONSTRAINT questions_status_check
        CHECK (status IN ('PENDING', 'ANSWERED')),

    answer VARCHAR(5000),

    parent_question_id TEXT
        REFERENCES public.questions(id)
        ON DELETE SET NULL,

    privacy_confirmed_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    /*
     * 회원과 비회원 중 정확히 하나만 작성자가 되어야 합니다.
     * 비회원 데이터만 만료일을 가집니다.
     */
    CONSTRAINT questions_owner_check
        CHECK (
            (
                user_id IS NOT NULL
                AND guest_id IS NULL
                AND expires_at IS NULL
            )
            OR
            (
                user_id IS NULL
                AND guest_id IS NOT NULL
                AND BTRIM(guest_id) <> ''
                AND expires_at IS NOT NULL
                AND expires_at > created_at
            )
        ),

    CONSTRAINT questions_display_name_not_blank_check
        CHECK (BTRIM(display_name) <> ''),

    CONSTRAINT questions_title_not_blank_check
        CHECK (BTRIM(title) <> ''),

    CONSTRAINT questions_content_not_blank_check
        CHECK (BTRIM(content) <> ''),

    /*
     * 답변 대기 상태에는 답변이 없어야 하고,
     * 답변 완료 상태에는 답변이 있어야 합니다.
     */
    CONSTRAINT questions_answer_status_check
        CHECK (
            (status = 'PENDING' AND answer IS NULL)
            OR
            (
                status = 'ANSWERED'
                AND answer IS NOT NULL
                AND BTRIM(answer) <> ''
            )
        ),

    CONSTRAINT questions_parent_not_self_check
        CHECK (
            parent_question_id IS NULL
            OR parent_question_id <> id
        )
);


/* =========================================================
 * 4. 질문 댓글
 * ========================================================= */

CREATE TABLE IF NOT EXISTS public.question_comments (
    id TEXT PRIMARY KEY
        DEFAULT ('comment-' || gen_random_uuid()::TEXT),

    question_id TEXT NOT NULL
        REFERENCES public.questions(id)
        ON DELETE CASCADE,

    user_id BIGINT
        REFERENCES public.users(id)
        ON DELETE CASCADE,

    guest_id VARCHAR(100),

    display_name VARCHAR(30) NOT NULL,
    content VARCHAR(1000) NOT NULL,

    /*
     * 회원 댓글은 NULL이고 비회원 댓글만 Hash가 필요합니다.
     */
    password_hash TEXT,

    author_role VARCHAR(10) NOT NULL
        CONSTRAINT question_comments_author_role_check
        CHECK (author_role IN ('GUEST', 'USER', 'ADMIN')),

    is_official_answer BOOLEAN NOT NULL DEFAULT FALSE,

    expires_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT question_comments_owner_check
        CHECK (
            (
                user_id IS NOT NULL
                AND guest_id IS NULL
                AND password_hash IS NULL
                AND expires_at IS NULL
                AND author_role IN ('USER', 'ADMIN')
            )
            OR
            (
                user_id IS NULL
                AND guest_id IS NOT NULL
                AND BTRIM(guest_id) <> ''
                AND password_hash IS NOT NULL
                AND expires_at IS NOT NULL
                AND expires_at > created_at
                AND author_role = 'GUEST'
            )
        ),

    CONSTRAINT question_comments_display_name_not_blank_check
        CHECK (BTRIM(display_name) <> ''),

    CONSTRAINT question_comments_content_not_blank_check
        CHECK (BTRIM(content) <> ''),

    /*
     * 공식 답변 댓글은 관리자만 등록할 수 있습니다.
     * 현재 Backend는 questions.answer를 사용하므로 기본값은 FALSE입니다.
     */
    CONSTRAINT question_comments_official_answer_check
        CHECK (
            is_official_answer = FALSE
            OR author_role = 'ADMIN'
        )
);


/* =========================================================
 * 5. 알림
 * ========================================================= */

CREATE TABLE IF NOT EXISTS public.notifications (
    id TEXT PRIMARY KEY
        DEFAULT ('notification-' || gen_random_uuid()::TEXT),

    user_id BIGINT
        REFERENCES public.users(id)
        ON DELETE CASCADE,

    guest_id VARCHAR(100),

    type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,

    severity VARCHAR(10) NOT NULL DEFAULT 'info'
        CONSTRAINT notifications_severity_check
        CHECK (severity IN ('info', 'success', 'warning', 'error')),

    target_type VARCHAR(50),
    target_id TEXT,

    category VARCHAR(20)
        CONSTRAINT notifications_category_check
        CHECK (
            category IS NULL
            OR category IN ('housing', 'labor', 'consumer')
        ),

    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT notifications_owner_check
        CHECK (
            (
                user_id IS NOT NULL
                AND guest_id IS NULL
                AND expires_at IS NULL
            )
            OR
            (
                user_id IS NULL
                AND guest_id IS NOT NULL
                AND BTRIM(guest_id) <> ''
                AND expires_at IS NOT NULL
                AND expires_at > created_at
            )
        ),

    CONSTRAINT notifications_type_not_blank_check
        CHECK (BTRIM(type) <> ''),

    CONSTRAINT notifications_title_not_blank_check
        CHECK (BTRIM(title) <> ''),

    CONSTRAINT notifications_message_not_blank_check
        CHECK (BTRIM(message) <> '')
);


/* =========================================================
 * 6. 질문·법률 분석 이력
 * ========================================================= */

CREATE TABLE IF NOT EXISTS public.query_history (
    id TEXT PRIMARY KEY
        DEFAULT ('history-' || gen_random_uuid()::TEXT),

    user_id BIGINT
        REFERENCES public.users(id)
        ON DELETE CASCADE,

    guest_id VARCHAR(100),

    type VARCHAR(30) NOT NULL
        CONSTRAINT query_history_type_check
        CHECK (type IN ('legal_analysis', 'user_question')),

    /*
     * user_question이면 question ID,
     * legal_analysis이면 요청 또는 실행 ID를 저장합니다.
     * 대상 종류가 다르므로 FK는 설정하지 않습니다.
     */
    target_id TEXT NOT NULL,

    category VARCHAR(20) NOT NULL
        CONSTRAINT query_history_category_check
        CHECK (category IN ('housing', 'labor', 'consumer')),

    title TEXT NOT NULL,
    expires_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT query_history_owner_check
        CHECK (
            (
                user_id IS NOT NULL
                AND guest_id IS NULL
                AND expires_at IS NULL
            )
            OR
            (
                user_id IS NULL
                AND guest_id IS NOT NULL
                AND BTRIM(guest_id) <> ''
                AND expires_at IS NOT NULL
                AND expires_at > created_at
            )
        ),

    CONSTRAINT query_history_target_not_blank_check
        CHECK (BTRIM(target_id) <> ''),

    CONSTRAINT query_history_title_not_blank_check
        CHECK (BTRIM(title) <> '')
);


/* =========================================================
 * 7. 관리자 감사 로그
 * ========================================================= */

CREATE TABLE IF NOT EXISTS public.audit_logs (
    id BIGSERIAL PRIMARY KEY,

    /*
     * 관리자 계정이 삭제돼도 감사 기록 자체는 보존합니다.
     */
    actor_user_id BIGINT
        REFERENCES public.users(id)
        ON DELETE SET NULL,

    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id TEXT NOT NULL,

    reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT audit_logs_action_not_blank_check
        CHECK (BTRIM(action) <> ''),

    CONSTRAINT audit_logs_target_type_not_blank_check
        CHECK (BTRIM(target_type) <> ''),

    CONSTRAINT audit_logs_target_id_not_blank_check
        CHECK (BTRIM(target_id) <> '')
);


COMMIT;