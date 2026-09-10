-- Repository reference: PostgreSQL $n bind parameters, never interpolate actor/input.
-- PREPARE names make examples executable in a disposable test connection.
-- $1/$2 MUST come from server-verified identity, never request JSON/header directly.
PREPARE saved_owner(TEXT, TEXT, BIGINT) AS
SELECT c.* FROM public.users u
JOIN public.saved_conversations c ON c.user_id=u.id
WHERE u.actor_issuer=$1 AND u.actor_subject=$2 AND c.id=$3
  AND (c.expires_at IS NULL OR c.expires_at > now());

-- Lock before allocating insertion order, checking retries and inserting BOTH messages
-- plus their source links in ONE transaction. Recheck authorization under this lock.
PREPARE saved_lock(TEXT, TEXT, BIGINT) AS
SELECT c.id FROM public.users u
JOIN public.saved_conversations c ON c.user_id=u.id
WHERE u.actor_issuer=$1 AND u.actor_subject=$2 AND c.id=$3
  AND c.save_state='selected'
  AND (c.expires_at IS NULL OR c.expires_at > now())
FOR UPDATE OF c;

-- First question + latest 3 COMPLETE pairs (2-3 turns, not merely 2-3 rows).
-- Failed/stopped and unclassified legacy rows do not masquerade as complete turns.
PREPARE saved_context(TEXT, TEXT, BIGINT) AS
WITH owner AS MATERIALIZED (
    SELECT c.id FROM public.saved_conversations c
    JOIN public.users u ON u.id=c.user_id
    WHERE u.actor_issuer=$1 AND u.actor_subject=$2 AND c.id=$3
      AND (c.expires_at IS NULL OR c.expires_at > now())
), recent AS MATERIALIZED (
    SELECT a.id, a.execution_key FROM public.saved_messages a
    WHERE a.conversation_id=(SELECT id FROM owner)
      AND a.role='assistant' AND a.processing_status='completed'
      AND EXISTS (SELECT 1 FROM public.saved_messages q
          WHERE q.conversation_id=a.conversation_id AND q.execution_key=a.execution_key
            AND q.role='user' AND q.processing_status='completed')
    ORDER BY a.id DESC LIMIT 3
), selected AS (
    (SELECT m.id FROM public.saved_messages m
     WHERE m.conversation_id=(SELECT id FROM owner) AND m.role='user'
     ORDER BY m.id LIMIT 1)
    UNION
    SELECT m.id FROM recent r JOIN public.saved_messages m
      ON m.conversation_id=(SELECT id FROM owner) AND m.execution_key=r.execution_key
    WHERE m.processing_status='completed'
)
SELECT m.id, m.role, m.execution_key, left(m.content, 4000) AS content,
       CASE WHEN m.role='assistant' THEN
           m.snapshot->'payload'->'follow_up_questions' END AS follow_up_questions,
       ARRAY(SELECT s.id FROM public.saved_message_sources s
             WHERE s.message_id=m.id ORDER BY s.id LIMIT 20) AS source_link_ids
FROM selected x JOIN public.saved_messages m ON m.id=x.id ORDER BY m.id;

-- History restoration: paginate all statuses including legacy, return stored JSON.
-- $4 is last seen message id (0 for first page); next page uses last returned id.
PREPARE saved_restore(TEXT, TEXT, BIGINT, BIGINT) AS
SELECT m.* FROM public.saved_messages m
JOIN public.saved_conversations c ON c.id=m.conversation_id
JOIN public.users u ON u.id=c.user_id
WHERE u.actor_issuer=$1 AND u.actor_subject=$2 AND c.id=$3 AND m.id>$4
  AND (c.expires_at IS NULL OR c.expires_at > now())
ORDER BY m.id LIMIT 50;

-- Explicit user deletion only. Authorization is part of the DELETE itself.
-- Cascades remove saved messages + source LINKS, never legal_documents/legal_chunks.
PREPARE saved_delete(TEXT, TEXT, BIGINT) AS
DELETE FROM public.saved_conversations c USING public.users u
WHERE u.id=c.user_id AND u.actor_issuer=$1 AND u.actor_subject=$2 AND c.id=$3
RETURNING c.id;
