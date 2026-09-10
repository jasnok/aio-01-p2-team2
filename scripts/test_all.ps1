$ErrorActionPreference = "Stop"

$venvPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython -m pytest
} else {
    python -m pytest
}

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
