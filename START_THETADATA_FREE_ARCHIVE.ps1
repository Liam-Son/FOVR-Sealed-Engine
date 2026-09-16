$ErrorActionPreference = "Stop"
Write-Host "FOVR ThetaData FREE forward archive"
Write-Host "Requirement: Theta Terminal running on the local machine with a free account."
Write-Host "Free tier currently provides 1 year EOD stocks/options with a rate limit."

if (-not (Test-Path ".venv")) { py -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install pandas pyarrow numpy requests

if (Test-Path ".\thetadata_free_fovr_pipeline.py") {
    & .\.venv\Scripts\python.exe .\thetadata_free_fovr_pipeline.py
} else {
    throw "Missing thetadata_free_fovr_pipeline.py"
}
