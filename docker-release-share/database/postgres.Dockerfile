# 실제 법령·판례·상담사례와 pgvector 임베딩을 포함한 읽기/쓰기 PostgreSQL 이미지입니다.
# 회원 정보와 질의 이력은 seed에 포함하지 않으며, 새 볼륨에서만 초기 데이터가 복원됩니다.
FROM pgvector/pgvector:pg16

COPY database/migrations/ /docker-entrypoint-initdb.d/
COPY database/seed/010_legal_search_data.sql.gz /docker-entrypoint-initdb.d/010_legal_search_data.sql.gz
