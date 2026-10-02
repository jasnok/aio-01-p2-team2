# 검색 근거의 사람 검토 입력 계약

검토 풀에 없는 문서 점수가 ideal DCG에 포함되어 NDCG를 바꾸던 오류를 수정했습니다. 검토 대상 밖의 질문/문서, 불리언·문자열·범위 밖 점수는 거부합니다. ideal DCG는 해당 질문의 검토 풀에 속한 문서 점수만 사용합니다.

검색 결과는 문서 ID·제목·청크 목록의 길이가 같아야 하며 문서 ID는 중복 없는 양의 정수입니다. 길이 불일치가 `zip`에서 조용히 사라지는 경로를 차단합니다. 자연어 질문 ID의 중복과 잘못된 필드도 거부합니다. 정확 식별자 검색이나 오류 레코드는 사람 자연어 관련성 지표에 섞지 않습니다.

부분 점수 저장은 허용하되 모든 후보가 검토된 질문만 집계합니다. 후보가 없는 질문은 사람 검토 완료로 처리하지 않고 `empty_candidate_queries`로 별도 보고합니다. `pending_queries`에는 미완료 질문을 포함합니다. 따라서 보고된 평균의 분모는 검토 완료 질문이며, 전체 질문 품질 평가로 해석하면 안 됩니다.

지표는 pooled retrieved-document relevance입니다. 문서의 여러 청크 중 가장 낮은 관련성을 평가하며, 청크 선택 차이·corpus recall·법률 정확도·최신성을 측정하지 않습니다. 부분 검토를 품질 0점으로 대체하거나 실제 사람 점수를 생성하지 않습니다.

```powershell
.\.venv\Scripts\python.exe scripts/review_retrieval.py
.\.venv\Scripts\python.exe scripts/review_retrieval.py --labels relevance-labels.json
.\.venv\Scripts\python.exe -m pytest tests/test_retrieval_review.py -q
```

기존 실제 검색 자료 30건 중 자연어 검토 대상 15개 질문의 검토표를 다시 생성하여 입력 호환성을 확인했습니다. 실제 사람 관련성 채점은 미완료입니다. 합성 회귀 테스트의 점수는 계약 검증용이며 포트폴리오 품질 결과로 사용하지 않습니다.
