// Run on an in-memory PostgreSQL WASM instance; NEVER connects to DATABASE_URL.
// node .../test_saved_conversation_migration.mjs <absolute PGlite dist/index.js>
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
const { PGlite } = await import(pathToFileURL(process.argv[2]).href);
const read = path => readFile(new URL(path, import.meta.url), 'utf8');
const baseline = await read('../migrations/003_saved_conversations.sql');
const migration = await read('../migrations/006_saved_conversation_reuse.sql');
const queries = await read('../scripts/saved_conversation_queries.sql');
let checks = 0;
const ok = (condition, label) => { assert.ok(condition, label); checks++; console.log('PASS ' + label); };
async function rejected(db, sql, code) {
    await assert.rejects(db.exec(sql), e => e.code === code);
    checks++;
}
async function setup() {
    const db = new PGlite();
    await db.exec(`CREATE TABLE legal_documents(id bigserial PRIMARY KEY);
      CREATE TABLE legal_chunks(id bigserial PRIMARY KEY);
      INSERT INTO legal_documents DEFAULT VALUES; INSERT INTO legal_chunks DEFAULT VALUES;`);
    await db.exec(baseline);
    return db;
}
const db = await setup();
console.log((await db.query('select version()')).rows[0]);
await db.exec(`INSERT INTO users(anonymous_key) VALUES ('legacy');
 INSERT INTO saved_conversations(user_id,title,source_request_id) VALUES (1,'old','old-request');
 INSERT INTO saved_messages(conversation_id,role,content) VALUES (1,'user','original question'),(1,'assistant','original answer');
 INSERT INTO saved_message_sources(message_id,document_id,chunk_id,source_url) VALUES (2,1,1,'https://example.test/source');`);
const original = (await db.query('SELECT * FROM saved_message_sources')).rows;
await db.exec(migration);
ok((await db.query('SELECT count(*)::int AS n FROM saved_messages')).rows[0].n === 2, 'legacy message rows preserved');
assert.deepEqual((await db.query('SELECT * FROM saved_message_sources')).rows, original);
await db.exec(`INSERT INTO saved_message_sources(message_id,source_url) VALUES
 (2,'https://example.test/a'),(2,'https://example.test/b')`);
await rejected(db, `INSERT INTO saved_message_sources(message_id,source_url) VALUES (2,'https://example.test/a')`, '23505');
ok((await db.query('SELECT count(*)::int AS n FROM saved_message_sources')).rows[0].n === 3, 'multiple URL-only sources retained, duplicate rejected');
ok((await db.query('SELECT processing_status FROM saved_messages')).rows.every(x => x.processing_status === 'legacy'), 'legacy not falsely completed');
ok((await db.query('SELECT actor_subject FROM users')).rows[0].actor_subject === null, 'legacy identity not claimed');
await db.exec(`INSERT INTO saved_messages(conversation_id,role,content) VALUES (1,'assistant','old writer compatible');`);
ok(true, '003-style insert still supported');
await rejected(db, migration, 'P0001'); await db.exec('ROLLBACK');
ok((await db.query('SELECT count(*)::int AS n FROM saved_message_sources')).rows[0].n === 3, 'rerun fails safely without data loss');
await rejected(db, `UPDATE users SET actor_issuer='trusted' WHERE id=1`, '23514');
await db.exec(`UPDATE users SET actor_issuer='trusted',actor_subject='member-a' WHERE id=1;
 INSERT INTO users(anonymous_key,actor_issuer,actor_subject) VALUES ('opaque-b','trusted','member-b');`);
await rejected(db, `INSERT INTO users(anonymous_key,actor_issuer,actor_subject) VALUES ('different','trusted','member-a')`, '23505');
await rejected(db, `INSERT INTO saved_conversations(user_id,title,source_request_id,save_state) VALUES (1,'bad','bad','selected')`, '23514');
await db.exec(`INSERT INTO saved_conversations(user_id,title,source_request_id,save_state,category,saved_at)
 VALUES (1,'new','new-request','selected','housing',now());`);
const cid = (await db.query("SELECT id FROM saved_conversations WHERE source_request_id='new-request'")).rows[0].id;
for (let i = 0; i < 5; i++) {
    for (const role of ['user', 'assistant']) {
        await db.query(`INSERT INTO saved_messages(conversation_id,role,content,execution_key,processing_status,snapshot)
          VALUES ($1,$2,$3,$4,'completed',$5::jsonb)`, [cid, role, `${role}-${i}`, `run:${i}`, JSON.stringify({ version: 1, payload: { follow_up_questions: ['clarify ' + i], answer: 'restorable' } })]);
    }
}
await rejected(db, `INSERT INTO saved_messages(conversation_id,role,content,execution_key,processing_status,snapshot)
 VALUES (${cid},'assistant','duplicate','run:4','completed','{"version":1,"payload":{}}')`, '23505');
await rejected(db, `INSERT INTO saved_messages(conversation_id,role,content,execution_key,processing_status,snapshot)
 VALUES (1,'assistant','cross conversation duplicate','run:4','completed','{"version":1,"payload":{}}')`, '23505');
for (const snapshot of ['null', '{}', '{"version":1}', '{"version":1,"payload":null}']) {
    await rejected(db, `INSERT INTO saved_messages(conversation_id,role,content,execution_key,processing_status,snapshot)
      VALUES (${cid},'assistant','bad','run:bad','completed','${snapshot}')`, '23514');
}
await db.exec(`INSERT INTO saved_messages(conversation_id,role,content,execution_key,processing_status,snapshot)
 VALUES (${cid},'assistant','failed','run:failure','failed','{"version":1,"payload":{}}'),
 (${cid},'assistant','incomplete pair','run:unpaired','completed','{"version":1,"payload":{}}');`);
await db.exec(queries);
const context = (await db.exec(`EXECUTE saved_context('trusted','member-a',${cid})`))[0].rows;
ok(context.length === 7 && context[0].content === 'user-0' && context.at(-1).content === 'assistant-4', 'first question + 3 complete pairs, failed/unpaired excluded');
ok((await db.exec(`EXECUTE saved_context('trusted','member-b',${cid})`))[0].rows.length === 0, 'other actor cannot read context');
ok((await db.exec(`EXECUTE saved_restore('trusted','member-b',${cid},0)`))[0].rows.length === 0, 'other actor cannot restore');
ok((await db.exec(`EXECUTE saved_delete('trusted','member-b',${cid})`))[0].rows.length === 0, 'other actor cannot delete');
const restored = (await db.exec(`EXECUTE saved_restore('trusted','member-a',${cid},0)`))[0].rows;
ok(restored[0].snapshot.payload.answer === 'restorable', 'JSON snapshot restored');
await db.exec(`UPDATE saved_conversations SET created_at=now()-interval '2 days',saved_at=now()-interval '2 days',expires_at=now()-interval '1 day' WHERE id=${cid}`);
ok((await db.exec(`EXECUTE saved_restore('trusted','member-a',${cid},0)`))[0].rows.length === 0, 'expired excluded from restore');
ok((await db.exec(`EXECUTE saved_context('trusted','member-a',${cid})`))[0].rows.length === 0, 'expired excluded from context');
await db.exec(`EXECUTE saved_delete('trusted','member-a',1)`);
ok((await db.query('SELECT count(*)::int AS n FROM saved_message_sources')).rows[0].n === 0, 'delete cascades source links');
ok((await db.query('SELECT count(*)::int AS n FROM saved_messages WHERE conversation_id=1')).rows[0].n === 0, 'delete cascades messages');
ok((await db.query('SELECT count(*)::int AS n FROM legal_documents')).rows[0].n === 1, 'original document preserved');
ok((await db.query('SELECT count(*)::int AS n FROM legal_chunks')).rows[0].n === 1, 'original chunk preserved');
await db.close();

const drift = await setup();
await drift.exec('ALTER TABLE saved_messages DROP CONSTRAINT saved_messages_conversation_id_fkey');
await rejected(drift, migration, 'P0001'); await drift.exec('ROLLBACK');
ok((await drift.query("SELECT count(*)::int AS n FROM information_schema.columns WHERE table_name='users' AND column_name='actor_subject'")).rows[0].n === 0, 'schema drift aborts before additions');
await drift.close();
const optional004 = await read('../migrations/004_web_features.sql').catch(e => { if (e.code === 'ENOENT') return null; throw e; });
if (optional004) {
    const with004 = await setup();

    const webIndexes = await read(
        '../migrations/005_web_feature_indexes.sql'
    );

    await with004.exec(optional004);
    await with004.exec(webIndexes);
    await with004.exec(migration);

    const columns = await with004.query(`
        SELECT count(*)::int AS n
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'users'
          AND column_name IN ('role', 'actor_subject')
    `);

    ok(
        columns.rows[0].n === 2,
        '003 + 004 + 005 web indexes + 006 compatible'
    );

    const indexes = await with004.query(`
        SELECT count(*)::int AS n
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname IN (
              'idx_questions_status_created',
              'saved_conversations_owner_latest_idx'
          )
    `);

    ok(
        indexes.rows[0].n === 2,
        'web and saved conversation indexes coexist'
    );

    await with004.close();
} else {
    throw new Error(
        '004_web_features.sql is required for integrated validation'
    );
}
const atomic = await setup();
await rejected(atomic, migration.replace('COMMIT;', 'SELECT 1/0; COMMIT;'), '22012');
await atomic.exec('ROLLBACK');
ok((await atomic.query("SELECT count(*)::int AS n FROM information_schema.columns WHERE table_name='users' AND column_name='actor_subject'")).rows[0].n === 0, 'late failure rolls all DDL back');
ok((await atomic.query("SELECT count(*)::int AS n FROM pg_constraint WHERE conrelid='saved_message_sources'::regclass AND pg_get_constraintdef(oid)='UNIQUE NULLS NOT DISTINCT (message_id, document_id, chunk_id)'")).rows[0].n === 1, 'late failure restores original source constraint');
await atomic.close();
console.log(`PASS ${checks} assertions (disposable PostgreSQL; not shared DB)`);
