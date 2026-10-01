"""15 verifiable identifier lookups + 15 natural questions awaiting human labels.

IDs refer to the 2026-09-14 seed. Identifier hits are not legal answer accuracy.
"""

IDENTIFIERS = {
    "housing": [("민법", 1), ("주택임대차보호법", 2), ("주택임대차보호법 시행령", 3),
                ("2016다244224", 11), ("2024다326398", 13)],
    "labor": [("근로기준법", 4), ("근로자퇴직급여 보장법", 5), ("2004다29736", 15),
              ("2015도15317", 16), ("2023도188", 17)],
    "consumer": [("전자상거래 등에서의 소비자보호에 관한 법률", 6), ("소비자기본법", 7),
                 ("형법", 8), ("2008다39786", 20), ("2020다288375", 23)],
}

NATURAL_QUESTIONS = {
    "housing": [
        "월세 계약이 끝나 집을 인도했는데 집주인이 보증금을 돌려주지 않습니다.",
        "전입신고를 하고 거주하다가 이사했습니다. 임차권등기 전에 점유를 잃으면 대항력에 어떤 영향이 있나요?",
        "계약 갱신을 요청했는데 집주인이 직접 살겠다며 거절했습니다. 관련 자료를 찾고 싶습니다.",
        "보증금을 돌려받지 못해 내용증명을 보내려고 합니다. 어떤 근거를 확인해야 하나요?",
        "주택이 경매에 넘어갔습니다. 임차인의 우선변제권 관련 자료를 찾고 싶습니다.",
    ],
    "labor": [
        "주 40시간씩 2년 일하고 퇴사했는데 퇴직금을 못 받았습니다. 지급 요건을 확인하고 싶습니다.",
        "퇴사한 지 한 달이 지났는데 마지막 달 임금을 받지 못했습니다. 관련 근거를 확인하고 싶습니다.",
        "재직 중 중간정산한 퇴직금의 지급이 지연됐습니다. 지연이자 관련 판례를 찾고 싶습니다.",
        "근로계약서를 쓰지 않고 일했습니다. 근로자 지위와 임금 지급 관련 자료를 찾고 싶습니다.",
        "회사에서 해고 통보를 받았습니다. 해고 절차와 근로기준법을 확인하고 싶습니다.",
    ],
    "consumer": [
        "온라인 쇼핑몰에서 운동화를 샀는데 하자가 있어 수령 다음 날 환불을 요청했지만 거절당했습니다.",
        "인터넷 쇼핑몰에 대금을 지급했는데 상품이 배송되지 않았습니다. 취소와 환불 근거를 찾고 싶습니다.",
        "중고거래에서 정상 제품이라고 안내받았는데 고장 난 물건이 왔습니다. 손해배상 자료를 찾고 싶습니다.",
        "온라인 구매 후 3일 만에 반품을 요청했습니다. 청약철회 관련 법령을 확인하고 싶습니다.",
        "수리를 맡긴 제품이 다시 고장 났는데 업체가 추가 비용을 요구합니다. 소비자 상담사례를 찾고 싶습니다.",
    ],
}


def build_dataset():
    cases = []
    for category in IDENTIFIERS:
        for index, (query, document_id) in enumerate(IDENTIFIERS[category], 1):
            cases.append({"id": f"{category}-id-{index}", "category": category, "query": query,
                          "kind": "identifier", "expected_document_ids": [document_id], "label_status": "identifier_verified"})
        for index, query in enumerate(NATURAL_QUESTIONS[category], 1):
            cases.append({"id": f"{category}-natural-{index}", "category": category, "query": query,
                          "kind": "natural", "expected_document_ids": [], "label_status": "needs_human_review"})
    return cases
