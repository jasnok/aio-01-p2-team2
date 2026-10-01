$ErrorActionPreference = "Stop"
$env:BACKEND_MOCK_MODE = "true"
$env:LLM_PROVIDER = "mock"
$env:REDIS_ENABLED = "false"

$venvPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython -X utf8 -m pytest
} else {
    python -X utf8 -m pytest
}

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
