import os


# 로컬 Mock 회귀 테스트는 개발자의 frontend/.env 설정(api/mock)에 영향을 받지 않아야 한다.
os.environ["FRONTEND_DATA_MODE"] = "mock"
