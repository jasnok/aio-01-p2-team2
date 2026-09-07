"""법령·판례 DB 조회 Repository."""

from legal_mcp.infrastructure.database import get_connection


class LegalRepository:
    def search_cases(
        self,
        embedding: list[float],
        category: str,
        limit: int = 3,
    ) -> list[dict]:
        """판례 청크를 벡터 유사도로 검색한다."""

        sql = """
            SELECT
                d.id AS document_id,
                d.case_number,
                d.case_name,
                d.court,
                d.decided_at,
                d.judgment_result,
                d.summary,
                d.source_name,
                d.source_url,
                c.content AS chunk_content,
                1 - (c.embedding <=> %s::vector) AS similarity
            FROM legal_chunks AS c
            JOIN legal_documents AS d
                ON d.id = c.document_id
            WHERE d.document_type = 'CASE'
              AND d.category = %s
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        embedding,
                        category,
                        embedding,
                        limit,
                    ),
                )
                return cur.fetchall()
    def get_case_detail(self, document_id: int) -> dict | None:
        """판례 문서의 상세 정보를 조회한다."""

        sql = """
            SELECT
                id AS document_id,
                case_number,
                case_name,
                court,
                decided_at,
                judgment_result,
                summary,
                content,
                source_name,
                source_url
            FROM legal_documents
            WHERE id = %s
              AND document_type = 'CASE'
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (document_id,))
                return cur.fetchone()
    def get_law_article(
        self,
        law_name: str,
        article_number: str,
    ) -> dict | None:
        """법령명과 조문 번호로 법령 조문을 조회한다."""

        sql = """
            SELECT
                id AS document_id,
                law_name,
                article_number,
                title,
                content,
                effective_date,
                source_name,
                source_url
            FROM legal_documents
            WHERE document_type = 'LAW'
              AND law_name = %s
              AND article_number = %s
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (law_name, article_number))
                return cur.fetchone()
            
    def search_legal_documents(
        self,
        embedding: list[float],
        category: str,
        document_types: list[str],
        limit: int = 3,
    ) -> list[dict]:
        """법령과 판례 청크를 벡터 유사도로 통합 검색한다."""

        sql = """
            SELECT
                d.id AS document_id,
                d.document_type,
                d.law_name,
                d.article_number,
                d.title,
                d.case_number,
                d.case_name,
                d.court,
                d.decided_at,
                d.judgment_result,
                d.summary,
                d.source_name,
                d.source_url,
                c.content AS chunk_content,
                1 - (c.embedding <=> %s::vector) AS similarity
            FROM legal_chunks AS c
            JOIN legal_documents AS d
                ON d.id = c.document_id
            WHERE d.category = %s
              AND d.document_type = ANY(%s)
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        embedding,
                        category,
                        document_types,
                        embedding,
                        limit,
                    ),
                )
                return cur.fetchall()
    def search_laws(
        self,
        embedding: list[float],
        category: str,
        limit: int = 3,
    ) -> list[dict]:
        """법령 청크를 벡터 유사도로 검색한다."""

        sql = """
            SELECT
                d.id AS document_id,
                d.law_name,
                d.article_number,
                d.title,
                d.effective_date,
                d.source_name,
                d.source_url,
                c.content AS chunk_content,
                1 - (c.embedding <=> %s::vector) AS similarity
            FROM legal_chunks AS c
            JOIN legal_documents AS d
                ON d.id = c.document_id
            WHERE d.document_type = 'LAW'
              AND d.category = %s
              AND c.embedding IS NOT NULL
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        embedding,
                        category,
                        embedding,
                        limit,
                    ),
                )
                return cur.fetchall()
    def search_documents_by_keyword(
        self,
        query: str,
        category: str,
        document_types: list[str],
        limit: int = 3,
    ) -> list[dict]:
        """법령명·조문번호·사건번호·본문 키워드로 문서를 검색한다."""

        keyword = query.strip()
        pattern = f"%{keyword}%"

        sql = """
            WITH ranked_documents AS (
                SELECT DISTINCT ON (d.id)
                    d.id AS document_id,
                    d.document_type,
                    d.law_name,
                    d.article_number,
                    d.title,
                    d.case_number,
                    d.case_name,
                    d.court,
                    d.decided_at,
                    d.judgment_result,
                    d.summary,
                    d.effective_date,
                    d.source_name,
                    d.source_url,
                    COALESCE(c.content, d.content) AS chunk_content,

                    CASE
                        WHEN COALESCE(d.law_name, '') = %s
                          OR COALESCE(d.article_number, '') = %s
                          OR COALESCE(d.case_number, '') = %s
                            THEN 1.0

                        WHEN COALESCE(d.title, '') ILIKE %s
                          OR COALESCE(d.law_name, '') ILIKE %s
                          OR COALESCE(d.case_name, '') ILIKE %s
                            THEN 0.8

                        WHEN COALESCE(c.content, '') ILIKE %s
                            THEN 0.6

                        ELSE 0.5
                    END AS keyword_score

                FROM legal_documents AS d
                LEFT JOIN legal_chunks AS c
                    ON d.id = c.document_id

                WHERE d.category = %s
                  AND d.document_type = ANY(%s)
                  AND (
                      COALESCE(d.title, '') ILIKE %s
                      OR COALESCE(d.law_name, '') ILIKE %s
                      OR COALESCE(d.article_number, '') ILIKE %s
                      OR COALESCE(d.case_number, '') ILIKE %s
                      OR COALESCE(d.case_name, '') ILIKE %s
                      OR COALESCE(d.content, '') ILIKE %s
                      OR COALESCE(c.content, '') ILIKE %s
                  )

                ORDER BY
                    d.id,
                    keyword_score DESC,
                    c.chunk_index ASC
            )

            SELECT *
            FROM ranked_documents
            ORDER BY keyword_score DESC, document_id
            LIMIT %s
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        # keyword_score 계산
                        keyword,
                        keyword,
                        keyword,
                        pattern,
                        pattern,
                        pattern,
                        pattern,

                        # WHERE 조건
                        category,
                        document_types,
                        pattern,
                        pattern,
                        pattern,
                        pattern,
                        pattern,
                        pattern,
                        pattern,

                        # LIMIT
                        limit,
                    ),
                )
                return cur.fetchall()