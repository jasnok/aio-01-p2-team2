$ErrorActionPreference = "Stop"
python -m uvicorn legal_mcp.server:app --host 0.0.0.0 --port 8001
