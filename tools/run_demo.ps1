param(
    [int]$Port = 5000
)

$root = Resolve-Path "$PSScriptRoot\.."
$venvPython = Join-Path $root ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $python = $venvPython
} else {
    $python = "python"
}

Write-Host "Starting server with: $python app.py"
Start-Process -FilePath $python -ArgumentList "app.py" -WorkingDirectory $root | Out-Null

Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:$Port" | Out-Null

Write-Host "Demo started. Opened http://127.0.0.1:$Port"
Write-Host "Press Ctrl+C in the server window to stop."
