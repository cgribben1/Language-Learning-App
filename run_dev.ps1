if (-not $env:OPENAI_API_KEY) {
  Write-Host "OPENAI_API_KEY is not set for this PowerShell session."
  Write-Host "Set it first, then rerun this script."
  exit 1
}

Set-Location "C:\Users\curtu\docker_test\french_trainer"
python -m uvicorn app.main:app --reload --port 8090
