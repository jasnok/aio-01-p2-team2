# 성능 측정 출처와 재현 계약

이후 SDK 생성/획득 및 키워드 DB 비교는 측정 시작·종료 UTC 시각, Git HEAD, 미커밋 변경 여부, 실제 관련 소스의 SHA-256, Python·라이브러리 버전, constraints 해시를 기록합니다. Git HEAD만으로 실행 코드가 커밋과 동일하다고 가정하지 않습니다. 소스 해시는 CRLF를 LF로 정규화하며 측정 시작·종료 해시를 비교합니다.

DB 측정은 시작·종료 문서/청크 수, PostgreSQL 버전, 설정에 선언된 데이터 revision을 추가합니다. 규모가 같더라도 내용 불변을 증명하지 않으므로 `immutable_snapshot=false`입니다. revision도 선언값이며 자동 계산한 DB 내용 버전이 아닙니다. 결과 동등성은 기존 방식대로 각 쌍의 전체 결과를 비교합니다.

메타데이터는 Git 파일 목록, 환경 변수 전체, DB URL, API 키를 기록하지 않습니다. 패키지 버전과 고정된 관련 소스만 허용합니다. 형식 계약은 알 수 없는 메타데이터, 측정 중 변경 코드, 역전된 시각, 불완전하거나 달라진 DB 규모 기록을 거부합니다.

## 새 측정과 기존 자료

이전 측정 JSON은 유지하고 새 결과는 `embedding-client-acquisition-v2.json`, `keyword-connections-v2.json`에 별도로 보관합니다. 기존 결과에 시각·코드 정보를 소급해서 채우지 않습니다. 숫자 요약 생성기는 v2가 있으면 이를 선택하고, 없으면 기존 자료를 사용하여 미기록 안내를 유지합니다.

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_embedding_clients.py --output output/portfolio/embedding-client-acquisition-v2.json
.\.venv\Scripts\python.exe scripts/benchmark_keyword_connections.py --output output/portfolio/keyword-connections-v2.json
.\.venv\Scripts\python.exe scripts/build_portfolio_evidence.py
.\.venv\Scripts\python.exe scripts/build_portfolio_evidence.py --check
```

DB 명령은 접근 가능한 호스트 DB URL을 설정한 뒤 실행합니다. 출력에 URL이나 자격 증명은 기록하지 않습니다. SDK 측정은 가짜 키로 생성만 수행하며 모델 API 요청이 없습니다. DB 측정은 읽기 전용이며 모델 요청이 없습니다.

새 실제 측정에서는 DB 702문서·2,797청크, PostgreSQL 160015, 선언 revision `seed-702-v1`을 확인했습니다. 시작·종료 규모 및 실행 코드 해시가 동일했습니다. 미커밋 변경 포함 상태는 true로 기록했습니다. SDK 생성/재사용 중앙값은 399.75/0.0019ms이며, 키워드 조회 전후 중앙값은 주거 324.72/151.08ms, 노동 259.93/91.16ms, 소비자 485.01/316.53ms였습니다. 이전 측정과 환경을 완전히 같다고 가정하거나 시점 간 개선률을 산출하지 않습니다.

발표 화면은 선택한 측정의 시각·코드·환경·데이터 출처를 함께 보여줍니다. 원시 질문을 복사하지 않으며 전체 상담 지연·법률 정확도 미평가 안내는 유지합니다.
