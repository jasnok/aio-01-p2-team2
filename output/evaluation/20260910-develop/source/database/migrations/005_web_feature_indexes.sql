/*
 * 005_web_feature_indexes.sql
 *
 * 일반 웹 기능의 목록 조회, 소유자 조회, 정렬 및
 * 만료 데이터 정리를 위한 성능 인덱스입니다.
 *
 * 선행 마이그레이션:
 * - 001_init.sql
 * - 002_search_indexes.sql
 * - 003_saved_conversations.sql
 * - 004_web_features.sql
 */

BEGIN;

SET LOCAL lock_timeout = '5s';


/* =========================================================
 * 1. users
 * ========================================================= */

/*
 * 로그인 시 활성 회원을 역할별로 조회할 때 사용합니다.
 *
 * 이메일 중복 방지용 uq_users_email_lower 인덱스는
 * 데이터 무결성에 해당하므로 004_web_features.sql에 포함되어 있습니다.
 */
CREATE INDEX IF NOT EXISTS idx_users_role_active
    ON public.users (
        role,
        is_active
    )
    WHERE role IN ('USER', 'ADMIN');


/* =========================================================
 * 2. faqs
 * ========================================================= */

/*
 * 공개 FAQ 조회 정렬:
 * 1. 고정 FAQ 우선
 * 2. 표시 순서 오름차순
 * 3. 최근 수정 순
 */
CREATE INDEX IF NOT EXISTS idx_faqs_public_sort
    ON public.faqs (
        is_pinned DESC,
        display_order ASC,
        updated_at DESC,
        id
    )
    WHERE is_active = TRUE;


/*
 * 카테고리가 지정된 공개 FAQ 조회에 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_faqs_category_public_sort
    ON public.faqs (
        category,
        is_pinned DESC,
        display_order ASC,
        updated_at DESC,
        id
    )
    WHERE is_active = TRUE;


/*
 * 관리자 FAQ 전체 목록 조회에 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_faqs_admin_sort
    ON public.faqs (
        display_order ASC,
        updated_at DESC,
        id
    );


/* =========================================================
 * 3. questions
 * ========================================================= */

/*
 * 전체 질문 목록 조회에 사용합니다.
 *
 * PENDING이 ANSWERED보다 먼저 나오도록 status DESC를 사용합니다.
 * 같은 상태에서는 최신 질문이 먼저 나옵니다.
 */
CREATE INDEX IF NOT EXISTS idx_questions_status_created
    ON public.questions (
        status DESC,
        created_at DESC,
        id
    );


/*
 * 카테고리 및 상태별 질문 목록 조회에 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_questions_category_status_created
    ON public.questions (
        category,
        status DESC,
        created_at DESC,
        id
    );


/*
 * 회원이 작성한 질문을 최신순으로 조회할 때 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_questions_user_created
    ON public.questions (
        user_id,
        created_at DESC,
        id
    )
    WHERE user_id IS NOT NULL;


/*
 * 비회원이 작성한 질문을 최신순으로 조회할 때 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_questions_guest_created
    ON public.questions (
        guest_id,
        created_at DESC,
        id
    )
    WHERE guest_id IS NOT NULL;


/*
 * 다시 질문과 원본 질문의 연결을 조회할 때 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_questions_parent
    ON public.questions (
        parent_question_id,
        created_at ASC,
        id
    )
    WHERE parent_question_id IS NOT NULL;


/*
 * 만료된 비회원 질문을 정리할 때 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_questions_expires_at
    ON public.questions (
        expires_at
    )
    WHERE expires_at IS NOT NULL;


/* =========================================================
 * 4. question_comments
 * ========================================================= */

/*
 * 특정 질문의 댓글을 오래된 순서대로 조회할 때 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_question_comments_question_created
    ON public.question_comments (
        question_id,
        created_at ASC,
        id
    );


/*
 * 회원이 작성한 댓글을 조회할 때 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_question_comments_user_created
    ON public.question_comments (
        user_id,
        created_at DESC,
        id
    )
    WHERE user_id IS NOT NULL;


/*
 * 비회원이 작성한 댓글을 조회할 때 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_question_comments_guest_created
    ON public.question_comments (
        guest_id,
        created_at DESC,
        id
    )
    WHERE guest_id IS NOT NULL;


/*
 * 만료된 비회원 댓글을 정리할 때 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_question_comments_expires_at
    ON public.question_comments (
        expires_at
    )
    WHERE expires_at IS NOT NULL;


/* =========================================================
 * 5. notifications
 * ========================================================= */

/*
 * 회원 알림 목록 조회에 사용합니다.
 *
 * is_read ASC:
 * - FALSE인 미읽음 알림이 먼저 표시됩니다.
 *
 * 같은 읽음 상태에서는 최신 알림이 먼저 표시됩니다.
 */
CREATE INDEX IF NOT EXISTS idx_notifications_user_read_created
    ON public.notifications (
        user_id,
        is_read ASC,
        created_at DESC,
        id
    )
    WHERE user_id IS NOT NULL;


/*
 * 비회원 알림 목록 조회에 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_notifications_guest_read_created
    ON public.notifications (
        guest_id,
        is_read ASC,
        created_at DESC,
        id
    )
    WHERE guest_id IS NOT NULL;


/*
 * 회원의 미읽은 알림 개수 조회에 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
    ON public.notifications (
        user_id
    )
    WHERE user_id IS NOT NULL
      AND is_read = FALSE;


/*
 * 비회원의 미읽은 알림 개수 조회에 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_notifications_guest_unread
    ON public.notifications (
        guest_id
    )
    WHERE guest_id IS NOT NULL
      AND is_read = FALSE;


/*
 * 비회원 만료 알림 정리에 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_notifications_expires_at
    ON public.notifications (
        expires_at
    )
    WHERE expires_at IS NOT NULL;


/* =========================================================
 * 6. query_history
 * ========================================================= */

/*
 * 회원의 전체 이력을 최신순으로 조회할 때 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_query_history_user_created
    ON public.query_history (
        user_id,
        created_at DESC,
        id
    )
    WHERE user_id IS NOT NULL;


/*
 * 비회원의 전체 이력을 최신순으로 조회할 때 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_query_history_guest_created
    ON public.query_history (
        guest_id,
        created_at DESC,
        id
    )
    WHERE guest_id IS NOT NULL;


/*
 * 회원의 이력을 유형과 카테고리로 필터링할 때 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_query_history_user_type_category
    ON public.query_history (
        user_id,
        type,
        category,
        created_at DESC,
        id
    )
    WHERE user_id IS NOT NULL;


/*
 * 비회원의 이력을 유형과 카테고리로 필터링할 때 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_query_history_guest_type_category
    ON public.query_history (
        guest_id,
        type,
        category,
        created_at DESC,
        id
    )
    WHERE guest_id IS NOT NULL;


/*
 * 비회원 만료 이력 정리에 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_query_history_expires_at
    ON public.query_history (
        expires_at
    )
    WHERE expires_at IS NOT NULL;


/* =========================================================
 * 7. audit_logs
 * ========================================================= */

/*
 * 특정 관리자의 감사 기록을 최신순으로 조회할 때 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_created
    ON public.audit_logs (
        actor_user_id,
        created_at DESC,
        id
    )
    WHERE actor_user_id IS NOT NULL;


/*
 * 특정 질문이나 댓글의 감사 기록 조회에 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_audit_logs_target
    ON public.audit_logs (
        target_type,
        target_id,
        created_at DESC,
        id
    );


/*
 * 감사 로그를 시간순으로 조회하거나 보관 기간에 따라
 * 정리할 때 사용합니다.
 */
CREATE INDEX IF NOT EXISTS idx_audit_logs_created
    ON public.audit_logs (
        created_at DESC,
        id
    );


COMMIT;