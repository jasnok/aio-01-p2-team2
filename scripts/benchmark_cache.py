"""Local benchmark cache controls; never expose an admin reset API."""
import json
import subprocess
import time
from urllib.parse import urlencode


def cold_cache():
    # Restarting the single MCP process removes both in-memory TTL caches.
    subprocess.run(["docker", "compose", "restart", "mcp-server"], check=True, capture_output=True)
    container = subprocess.check_output(["docker", "compose", "ps", "-q", "mcp-server"], text=True).strip()
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        state = json.loads(subprocess.check_output(["docker", "inspect", "--format", "{{json .State}}", container], text=True))
        if state.get("Health", {}).get("Status") == "healthy":
            return {"method": "local_mcp_process_restart", "container": container,
                    "started_at": state["StartedAt"], "health": "healthy"}
        time.sleep(.5)
    raise RuntimeError("MCP did not become healthy after cache reset")


def prime_cache(base, category, query, request):
    params = urlencode({"category": category, "query": query, "top_k": 3})
    for route in ("laws", "cases", "consultations"):
        request(base, "/api/legal/" + route + "?" + params, {})
    return {"method": "same_question_search_routes_primed", "cache_hits_verified": False,
            "scope": "best-effort warm candidate; TTL or eviction may prevent hits"}
