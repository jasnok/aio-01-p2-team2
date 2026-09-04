"""세 전문 Agent의 변경이 적은 설정값을 한곳에서 관리합니다."""

from backend.app.agents.models import AgentProfile

LEGAL_READ_TOOLS = frozenset({"search_laws", "search_cases", "get_law_article"})

HOUSING_AGENT = AgentProfile("housing", "임대차·주거 Agent", "주거 법률 근거 검색", "임대차·보증금·계약 분쟁", "계약이 끝났는데 보증금을 받지 못했습니다.", "검색된 Evidence만 사용한다.", LEGAL_READ_TOOLS)
LABOR_AGENT = AgentProfile("labor", "근로·임금 Agent", "노동 법률 근거 검색", "임금·퇴직금·해고 분쟁", "퇴직했는데 퇴직금을 받지 못했습니다.", "검색된 Evidence만 사용한다.", LEGAL_READ_TOOLS)
CONSUMER_AGENT = AgentProfile("consumer", "소비자 Agent", "소비자 법률 근거 검색", "환불·미배송·중고거래 분쟁", "돈을 보냈는데 물건을 받지 못했습니다.", "검색된 Evidence만 사용한다.", LEGAL_READ_TOOLS)
