$ErrorActionPreference='Stop'
$Project=Split-Path $PSScriptRoot -Parent
$Config=Get-Content -Raw (Join-Path $Project 'installation.json') | ConvertFrom-Json
$env:REVIEW_HOME=$Config.DataRoot
$Python=Join-Path $Project '.venv\Scripts\python.exe'
$PidFile=Join-Path $Config.DataRoot 'processes.json'
if(Test-Path $PidFile){$Old=Get-Content -Raw $PidFile|ConvertFrom-Json;if((Get-Process -Id $Old.server -ErrorAction SilentlyContinue) -and (Get-Process -Id $Old.worker -ErrorAction SilentlyContinue)){return}; & (Join-Path $PSScriptRoot 'stop.ps1')}
$Server=Start-Process -FilePath $Python -ArgumentList '-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765' -WorkingDirectory $Project -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Config.DataRoot 'server.log') -RedirectStandardError (Join-Path $Config.DataRoot 'server-error.log')
$Worker=Start-Process -FilePath $Python -ArgumentList '-m backend.app.worker' -WorkingDirectory $Project -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Config.DataRoot 'worker.log') -RedirectStandardError (Join-Path $Config.DataRoot 'worker-error.log')
@{server=$Server.Id;worker=$Worker.Id;python=$Python} |ConvertTo-Json|Set-Content -Encoding utf8 $PidFile
