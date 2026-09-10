-- =========================================================
-- 법률홈닥터 사례집 DB 및 pgvector 적재 검증
-- =========================================================


-- 1. 카테고리별 문서·청크·Embedding 개수 확인
SELECT
    d.category,
    COUNT(DISTINCT d.id) AS document_count,
    COUNT(c.id) AS chunk_count,
    COUNT(c.embedding) AS embedding_count,
    COUNT(c.id) - COUNT(c.embedding) AS missing_embedding_count,
    MIN(vector_dims(c.embedding)) AS min_dimension,
    MAX(vector_dims(c.embedding)) AS max_dimension
FROM legal_documents d
LEFT JOIN legal_chunks c
    ON c.document_id = d.id
WHERE d.document_type = 'GUIDELINE'
  AND d.source_name = '법무부 법률홈닥터'
GROUP BY d.category
ORDER BY d.category;


-- 2. 사례별 상세 적재 상태 확인
SELECT
    d.id,
    d.external_id,
    d.category,
    d.document_type,
    d.title,
    d.source_name,
    d.source_type,
    d.raw_file,
    LENGTH(d.content) AS document_length,
    COUNT(c.id) AS chunk_count,
    COUNT(c.embedding) AS embedding_count
FROM legal_documents d
LEFT JOIN legal_chunks c
    ON c.document_id = d.id
WHERE d.document_type = 'GUIDELINE'
  AND d.source_name = '법무부 법률홈닥터'
GROUP BY
    d.id,
    d.external_id,
    d.category,
    d.document_type,
    d.title,
    d.source_name,
    d.source_type,
    d.raw_file,
    d.content
ORDER BY
    d.category,
    d.external_id;


-- 3. Embedding 누락 청크 확인
-- 정상 완료 시 0건이어야 합니다.
SELECT
    d.external_id,
    d.category,
    d.title,
    c.chunk_index,
    c.section_type,
    c.embedding_model,
    c.embedding_version
FROM legal_documents d
JOIN legal_chunks c
    ON c.document_id = d.id
WHERE d.document_type = 'GUIDELINE'
  AND d.source_name = '법무부 법률홈닥터'
  AND c.embedding IS NULL
ORDER BY
    d.category,
    d.external_id,
    c.chunk_index;


-- 4. Embedding 차원 확인
-- text-embedding-3-small 기본 차원은 1536이어야 합니다.
SELECT
    d.external_id,
    d.category,
    d.title,
    c.chunk_index,
    vector_dims(c.embedding) AS embedding_dimension,
    c.embedding_model
FROM legal_documents d
JOIN legal_chunks c
    ON c.document_id = d.id
WHERE d.document_type = 'GUIDELINE'
  AND d.source_name = '법무부 법률홈닥터'
ORDER BY
    d.category,
    d.external_id,
    c.chunk_index;


-- 5. 추출 본문 미리보기
SELECT
    d.external_id,
    d.category,
    d.title,
    c.chunk_index,
    c.section_type,
    LENGTH(c.content) AS content_length,
    LEFT(c.content, 500) AS content_preview
FROM legal_documents d
JOIN legal_chunks c
    ON c.document_id = d.id
WHERE d.document_type = 'GUIDELINE'
  AND d.source_name = '법무부 법률홈닥터'
ORDER BY
    d.category,
    d.external_id,
    c.chunk_index;


-- 6. 중복 external_id 확인
-- 정상 완료 시 결과가 없어야 합니다.
SELECT
    d.source_name,
    d.external_id,
    COUNT(*) AS duplicate_count
FROM legal_documents d
WHERE d.document_type = 'GUIDELINE'
  AND d.source_name = '법무부 법률홈닥터'
GROUP BY
    d.source_name,
    d.external_id
HAVING COUNT(*) > 1;


-- 7. 카테고리별 예상 문서 수와 비교
WITH expected(category, expected_count) AS (
    VALUES
        ('housing', 10),
        ('labor', 1),
        ('consumer', 3)
),
actual AS (
    SELECT
        category,
        COUNT(*) AS actual_count
    FROM legal_documents
    WHERE document_type = 'GUIDELINE'
      AND source_name = '법무부 법률홈닥터'
    GROUP BY category
)
SELECT
    e.category,
    e.expected_count,
    COALESCE(a.actual_count, 0) AS actual_count,
    CASE
        WHEN COALESCE(a.actual_count, 0) = e.expected_count
            THEN 'PASS'
        ELSE 'FAIL'
    END AS result
FROM expected e
LEFT JOIN actual a
    ON a.category = e.category
ORDER BY e.category;