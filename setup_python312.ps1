# TensorWatch Python 3.12 Setup Script
# This script creates a new virtual environment using Python 3.12

Write-Host "=== TenderWatch Python 3.12 Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check if Python 3.12 is available
Write-Host "Checking for Python 3.12..." -ForegroundColor Yellow
$python312 = py -3.12 --version 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "Python 3.12 found: $python312" -ForegroundColor Green
} else {
    Write-Host "Python 3.12 not found!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Creating virtual environment (.venv312)..." -ForegroundColor Yellow
py -3.12 -m venv .venv312

if ($LASTEXITCODE -eq 0) {
    Write-Host "Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "Failed to create virtual environment" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\.venv312\Scripts\Activate.ps1

Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
cd tenderwatch_app
pip install -r requirements.txt

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host "Environment ready to use!"
