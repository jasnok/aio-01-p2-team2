from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    code: str
    name: str
    icon: str
    description: str
    examples: tuple[str, ...]
    accent: str


CATEGORIES = {
    "housing": Category(
        "housing",
        "임대차·주거",
        "🏠",
        "보증금, 계약 종료·갱신, 주택 분쟁",
        ("보증금을 돌려받지 못했어요", "계약 갱신이 가능한가요?"),
        "#244f88",
    ),
    "labor": Category(
        "labor",
        "근로·임금",
        "💼",
        "임금 체불, 퇴직금, 해고, 근로계약",
        ("퇴직금을 받지 못했어요", "임금이 체불됐어요"),
        "#315f9d",
    ),
    "consumer": Category(
        "consumer",
        "소비자·중고거래",
        "🛒",
        "환불, 미배송, 상품 하자, 중고거래",
        ("돈을 보냈는데 물건이 안 와요", "환불을 거부당했어요"),
        "#3975ae",
    ),
}


def get_category(code: str) -> Category:
    try:
        return CATEGORIES[code]
    except KeyError as error:
        raise ValueError(f"지원하지 않는 카테고리입니다: {code}") from error
