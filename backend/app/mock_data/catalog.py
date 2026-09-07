"""Backend-owned catalogue copied from the Frontend Mock contract.

It intentionally contains guidance, not legal conclusions or real evidence.
"""
CATALOG = {
    "housing": {"name": "임대차·주거", "representative_questions": ["보증금은 언제 반환되나요?"], "terms": [["내용증명", "발송 내용과 시점을 확인하는 우편 방식입니다."], ["임차보증금", "임차인이 임대인에게 맡기는 금액입니다."]], "documents": ["임대차 계약서", "보증금 이체 내역", "대화 기록"], "next_actions": ["계약 종료 여부 확인", "반환 요청 기록 남기기"]},
    "labor": {"name": "근로·임금", "representative_questions": ["퇴직금을 받지 못했습니다."], "terms": [["계속근로기간", "근로자가 계속 일한 기간입니다."], ["임금체불", "정해진 때에 임금이 지급되지 않은 상태입니다."]], "documents": ["근로계약서", "급여명세서", "통장 입금 내역"], "next_actions": ["근로기간 확인", "지급 내역 확인"]},
    "consumer": {"name": "소비자·중고거래", "representative_questions": ["중고거래 환불이 가능한가요?"], "terms": [["청약철회", "일정한 거래에서 구매 의사를 철회하는 권리입니다."], ["하자", "상품이 약속된 상태를 갖추지 못한 경우입니다."]], "documents": ["판매 게시글", "결제 내역", "상품 사진"], "next_actions": ["거래 정보 보존", "판매자 요청 기록 남기기"]},
}
