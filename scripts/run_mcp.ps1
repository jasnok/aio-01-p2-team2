$ErrorActionPreference = "Stop"
$env:MCP_HOST = if ($env:MCP_HOST) { $env:MCP_HOST } else { "0.0.0.0" }
$env:MCP_PORT = if ($env:MCP_PORT) { $env:MCP_PORT } else { "8013" }
python -m legal_mcp.server
