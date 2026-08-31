from typing import Literal

from pydantic import BaseModel, Field


class FoodSearchRequest(BaseModel):
    region: Literal["서울", "부산"] = "서울"
    food_category: Literal["한식", "중식", "일식", "양식"] = "한식"
    max_price: int = Field(default=20000, ge=0)
    allergy: str = "없음"
    limit: int = Field(default=3, ge=1, le=10)


class FoodItem(BaseModel):
    restaurant_id: str
    name: str
    region: str
    food_category: str
    price: int
    allergy: list[str] = Field(default_factory=list)


class McpStatusResponse(BaseModel):
    status: Literal["ok"] = "ok"
    server: str
    url: str
    tools: list[str]


class FoodSearchResponse(BaseModel):
    success: Literal[True] = True
    request_id: str
    path: list[str]
    server: str
    tool: str
    items: list[FoodItem]
    count: int
    source: str
    allergy_notice: str = ""

