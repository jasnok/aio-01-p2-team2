"""8012 포트에서 독립 실행되는 음식 추천 Streamable HTTP MCP Server입니다."""

import os
from typing import Literal

from mcp.server.fastmcp import FastMCP


MCP_HOST = os.getenv("MCP_HOST", "192.100.200.72")
MCP_PORT = int(os.getenv("MCP_PORT", "8011"))

mcp = FastMCP(
    "mini-agent-food",
    instructions="지역, 음식 카테고리, 가격, 알러지 조건을 기반으로 음식점 정보를 제공하는 교육용 서버입니다.",
    host=MCP_HOST,
    port=MCP_PORT,
    stateless_http=True,
    json_response=True,
)


RESTAURANTS = [
    {
        "restaurant_id": "rest-seoul-001",
        "name": "서울김치마을",
        "region": "서울",
        "food_category": "한식",
        "price": 12000,
        "allergy": ["새우젓"],
    },
    {
        "restaurant_id": "rest-seoul-002",
        "name": "강남면옥",
        "region": "서울",
        "food_category": "한식",
        "price": 15000,
        "allergy": ["메밀"],
    },
    {
        "restaurant_id": "rest-seoul-003",
        "name": "홍대파스타",
        "region": "서울",
        "food_category": "양식",
        "price": 18000,
        "allergy": ["우유", "밀", "달걀"],
    },
    {
        "restaurant_id": "rest-busan-001",
        "name": "부산바다횟집",
        "region": "부산",
        "food_category": "일식",
        "price": 25000,
        "allergy": ["생선", "조개류"],
    },
    {
        "restaurant_id": "rest-busan-002",
        "name": "해운대밀면",
        "region": "부산",
        "food_category": "한식",
        "price": 10000,
        "allergy": ["밀", "달걀"],
    },
]


@mcp.tool()
def search_restaurants(
    region: Literal["서울", "부산"],
    food_category: Literal["한식", "중식", "일식", "양식"],
    max_price: int = 20000,
    allergy: str = "없음",
    limit: int = 3,
) -> dict:
    """조건에 맞는 음식점을 검색합니다."""

    normalized_region = region.strip()
    normalized_category = food_category.strip()
    normalized_allergy = allergy.strip()

    if not normalized_region:
        raise ValueError("region은 빈 문자열일 수 없습니다.")

    if not normalized_category:
        raise ValueError("food_category는 빈 문자열일 수 없습니다.")

    if max_price < 0:
        raise ValueError("max_price는 0 이상이어야 합니다.")

    if limit < 1:
        raise ValueError("limit은 1 이상이어야 합니다.")

    user_allergies = set()

    if normalized_allergy and normalized_allergy != "없음":
        user_allergies = {
            item.strip()
            for item in normalized_allergy.split(",")
            if item.strip()
        }

    matched_restaurants = []

    for restaurant in RESTAURANTS:
        if restaurant["region"] != normalized_region:
            continue

        if restaurant["food_category"] != normalized_category:
            continue

        if restaurant["price"] > max_price:
            continue

        restaurant_allergies = set(restaurant["allergy"])

        if user_allergies & restaurant_allergies:
            continue

        matched_restaurants.append(restaurant)

    return {
        "items": matched_restaurants[:limit],
        "count": len(matched_restaurants[:limit]),
        "source": "food-restaurant-catalog",
        "allergy_notice": (
            "알러지 정보는 교육용 데이터 기준입니다. "
            "실제 방문 전 음식점에 재료 및 교차 접촉 여부를 확인하세요."
        ),
    }


@mcp.tool()
def get_restaurant_detail(restaurant_id: str) -> dict:
    """음식점 ID로 상세 정보를 조회합니다."""

    normalized_id = restaurant_id.strip()

    if not normalized_id:
        raise ValueError("restaurant_id는 빈 문자열일 수 없습니다.")

    for restaurant in RESTAURANTS:
        if restaurant["restaurant_id"] == normalized_id:
            return {
                "item": restaurant,
                "source": "food-restaurant-catalog",
            }

    return {
        "item": None,
        "message": "해당 restaurant_id의 음식점을 찾을 수 없습니다.",
        "source": "food-restaurant-catalog",
    }


@mcp.resource("food://policy/allergy")
def allergy_policy() -> str:
    """교육용 알러지 안내 정책입니다."""

    return (
        "알러지 정보는 추천 필터링을 위한 교육용 참고 정보입니다. "
        "실제 음식점 방문 및 주문 전 재료와 교차 접촉 가능성을 반드시 확인하세요."
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")