$ErrorActionPreference = "Stop"

if (-not $env:TIINGO_API_KEY) {
    throw "TIINGO_API_KEY is required. The pipeline uses a free Tiingo account for historical delisted price backfills."
}

$target = "external\sp500-quantitative-dataset"

if (-not (Test-Path $target)) {
    git clone https://github.com/K0D1Z/sp500-quantitative-dataset.git $target
}

Push-Location $target
$env:TIINGO_API_KEY = $env:TIINGO_API_KEY

if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv sync
    uv run python main.py
} else {
    Write-Host "uv not installed. Using Docker path."
    docker compose up --build
}

Pop-Location
Write-Host "Free survivorship/PIT pipeline complete if upstream APIs succeeded."
