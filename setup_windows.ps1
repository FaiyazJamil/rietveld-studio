$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host 'Rietveld Studio: preparing Python desktop application and GSAS-II engine'
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    & py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install 64-bit Python 3.11 from python.org with the Python Launcher, then rerun setup.' }
}
$rietveldPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $rietveldPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip update failed.' }
& $rietveldPython -m pip install 'numpy==2.2.6' 'PyCifRW>=4.4' gitpython
if ($LASTEXITCODE -ne 0) { throw 'Engine prerequisites failed.' }
& $rietveldPython -m pip install -e '.[origin,dev]'
if ($LASTEXITCODE -ne 0) { throw 'Application dependencies failed.' }
& $rietveldPython scripts/bootstrap_engine.py
if ($LASTEXITCODE -ne 0) { throw 'GSAS-II setup failed. Read the error above; an existing GSAS-II installation can also be selected in the app.' }
& $rietveldPython scripts/generate_demo.py --destination examples/synthetic_nacl --gsas-path .engine/GSAS-II
if ($LASTEXITCODE -ne 0) { throw 'The engine installed but the synthetic demo check failed.' }
Write-Host 'Setup complete. Double-click launch_windows.bat to open the app.'

