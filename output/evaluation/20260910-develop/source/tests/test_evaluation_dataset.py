from collections import Counter
from tests.lawpath_100_dataset import cases


def test_evaluation_distribution_and_ids():
    rows=cases()
    assert len({r['id'] for r in rows}) == 100
    assert Counter(r['group'] for r in rows) == {
        '정상 요청':50,'정보 부족':20,'검색 결과 없음':10,'API 타임아웃':10,'인증 실패':5,'상충 지시':5}
    assert sum(r['mode']=='live' for r in rows)==75
    assert all(5<=len(r['question'])<=2000 for r in rows)
    assert rows[34]['id']=='T035' and '일시불' in rows[34]['question']
