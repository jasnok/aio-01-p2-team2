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