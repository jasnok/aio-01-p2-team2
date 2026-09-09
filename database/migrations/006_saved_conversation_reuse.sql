/* Opt-in saved conversations only. Requires reviewed 003 baseline, PostgreSQL 15+.
 * Does NOT apply 004, create accounts, claim old identities, expire or delete data.
 * Run once with psql -X -v ON_ERROR_STOP=1 -f ... after approval and backup.
 * Deliberately fail on rerun/column collisions instead of hiding schema drift.
 */
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
SET LOCAL search_path = public, pg_catalog;

-- Freeze inspected tables for this short, transactional migration.
LOCK TABLE public.users, public.saved_conversations, public.saved_messages,
    public.saved_message_sources IN ACCESS EXCLUSIVE MODE;

DO $$
DECLARE r record;
BEGIN
    IF current_setting('server_version_num')::integer < 150000 THEN
        RAISE EXCEPTION '006 requires PostgreSQL 15+';
    END IF;
    FOR r IN SELECT * FROM (VALUES
        ('users','id','bigint',true),
        ('users','anonymous_key','character varying(100)',false),
        ('users','created_at','timestamp with time zone',true),
        ('users','updated_at','timestamp with time zone',true),
        ('saved_conversations','id','bigint',true),
        ('saved_conversations','user_id','bigint',true),
        ('saved_conversations','title','text',true),
        ('saved_conversations','source_request_id','character varying(100)',true),
        ('saved_conversations','created_at','timestamp with time zone',true),
        ('saved_conversations','updated_at','timestamp with time zone',true),
        ('saved_messages','id','bigint',true),
        ('saved_messages','conversation_id','bigint',true),
        ('saved_messages','role','character varying(20)',true),
        ('saved_messages','content','text',true),
        ('saved_messages','created_at','timestamp with time zone',true),
        ('saved_message_sources','id','bigint',true),
        ('saved_message_sources','message_id','bigint',true),
        ('saved_message_sources','document_id','bigint',false),
        ('saved_message_sources','chunk_id','bigint',false),
        ('saved_message_sources','source_url','text',true),
        ('saved_message_sources','created_at','timestamp with time zone',true)
    ) AS baseline(tbl,col,typ,required) LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_attribute a
            WHERE a.attrelid = ('public.' || r.tbl)::regclass
              AND a.attname=r.col AND NOT a.attisdropped
              AND format_type(a.atttypid,a.atttypmod)=r.typ
              AND (NOT r.required OR a.attnotnull)) THEN
            RAISE EXCEPTION '006 baseline mismatch: %.%', r.tbl, r.col;
        END IF;
    END LOOP;
    -- Check definitions, not constraint names. Extra 004 user columns are allowed.
    FOR r IN SELECT * FROM (VALUES
        ('users','PRIMARY KEY (id)'),
        ('users','UNIQUE (anonymous_key)'),
        ('saved_conversations','PRIMARY KEY (id)'),
        ('saved_conversations','UNIQUE (source_request_id)'),
        ('saved_conversations','FOREIGN KEY (user_id) REFERENCES users(id)'),
        ('saved_messages','PRIMARY KEY (id)'),
        ('saved_messages','FOREIGN KEY (conversation_id) REFERENCES saved_conversations(id) ON DELETE CASCADE'),
        ('saved_message_sources','PRIMARY KEY (id)'),
        ('saved_message_sources','FOREIGN KEY (message_id) REFERENCES saved_messages(id) ON DELETE CASCADE'),
        ('saved_message_sources','FOREIGN KEY (document_id) REFERENCES legal_documents(id)'),
        ('saved_message_sources','FOREIGN KEY (chunk_id) REFERENCES legal_chunks(id)'),
        ('saved_message_sources','UNIQUE NULLS NOT DISTINCT (message_id, document_id, chunk_id)')
    ) AS baseline(tbl,def) LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_constraint c
            WHERE c.conrelid=('public.' || r.tbl)::regclass AND c.convalidated
              AND pg_get_constraintdef(c.oid)=r.def) THEN
            RAISE EXCEPTION '006 constraint mismatch: % / %', r.tbl, r.def;
        END IF;
    END LOOP;
END $$;

-- A trusted issuer + stable, verified subject maps to one existing numeric user.
-- No backfill from headers, mock IDs, email or anonymous_key.
ALTER TABLE public.users
    ADD COLUMN actor_issuer TEXT,
    ADD COLUMN actor_subject TEXT,
    ADD CONSTRAINT users_actor_pair_check CHECK (
        (actor_issuer IS NULL AND actor_subject IS NULL) OR
        (actor_issuer IS NOT NULL AND actor_subject IS NOT NULL
         AND length(btrim(actor_issuer)) BETWEEN 1 AND 200
         AND length(btrim(actor_subject)) BETWEEN 1 AND 200)),
    ADD CONSTRAINT users_actor_identity_key UNIQUE (actor_issuer, actor_subject);

ALTER TABLE public.saved_conversations
    ADD COLUMN category VARCHAR(20),
    ADD COLUMN save_state VARCHAR(20) NOT NULL DEFAULT 'legacy',
    ADD COLUMN saved_at TIMESTAMPTZ,
    ADD COLUMN expires_at TIMESTAMPTZ,
    ADD CONSTRAINT saved_conversations_category_check
        CHECK (category IN ('housing','labor','consumer')),
    ADD CONSTRAINT saved_conversations_save_check CHECK (
        (save_state='legacy' AND saved_at IS NULL AND expires_at IS NULL) OR
        (save_state='selected' AND saved_at IS NOT NULL AND category IS NOT NULL)),
    ADD CONSTRAINT saved_conversations_expiry_check
        CHECK (expires_at IS NULL OR (expires_at > saved_at AND expires_at > created_at));

-- Existing BIGSERIAL id is the durable insertion order: no speculative old turn backfill.
-- New writes serialize on the parent row and insert user then assistant atomically.
ALTER TABLE public.saved_messages
    ADD COLUMN execution_key VARCHAR(200),
    ADD COLUMN processing_status VARCHAR(20) NOT NULL DEFAULT 'legacy',
    ADD COLUMN snapshot JSONB,
    ADD CONSTRAINT saved_messages_storage_check CHECK (
        (processing_status='legacy' AND execution_key IS NULL AND snapshot IS NULL) OR
        (processing_status IN ('completed','failed','stopped')
         AND role IN ('user','assistant')
         AND execution_key IS NOT NULL AND length(btrim(execution_key)) > 0
         AND snapshot IS NOT NULL
         AND jsonb_typeof(snapshot)='object'
         AND snapshot ? 'version' AND snapshot->'version'='1'::jsonb
         AND snapshot ? 'payload' AND jsonb_typeof(snapshot->'payload')='object')),
    ADD CONSTRAINT saved_messages_execution_role_key
        UNIQUE (execution_key, role);

CREATE INDEX saved_conversations_owner_latest_idx
    ON public.saved_conversations (user_id, updated_at DESC, id DESC);
CREATE INDEX saved_messages_conversation_latest_idx
    ON public.saved_messages (conversation_id, id DESC);
CREATE INDEX saved_messages_completed_turn_idx
    ON public.saved_messages (conversation_id, id DESC)
    WHERE role='assistant' AND processing_status='completed';
CREATE INDEX saved_messages_first_question_idx
    ON public.saved_messages (conversation_id, id)
    WHERE role='user';

-- Existing key collapses every URL-only source to (message_id,NULL,NULL).
-- Widen it to preserve multiple external URLs without replacing rows or source FKs.
DO $$
DECLARE old_key name;
BEGIN
    SELECT conname INTO STRICT old_key FROM pg_constraint
    WHERE conrelid='public.saved_message_sources'::regclass
      AND pg_get_constraintdef(oid)=
          'UNIQUE NULLS NOT DISTINCT (message_id, document_id, chunk_id)';
    EXECUTE format('ALTER TABLE public.saved_message_sources DROP CONSTRAINT %I', old_key);
END $$;
ALTER TABLE public.saved_message_sources
    ADD CONSTRAINT saved_message_sources_reference_key
    UNIQUE NULLS NOT DISTINCT (message_id, document_id, chunk_id, source_url);

-- All original columns/values and source FK/delete semantics stay intact.
COMMIT;
