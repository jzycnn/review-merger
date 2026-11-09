$Project=Split-Path $PSScriptRoot -Parent
$Config=Get-Content -Raw (Join-Path $Project 'installation.json')|ConvertFrom-Json
$PidFile=Join-Path $Config.DataRoot 'processes.json'
if(Test-Path $PidFile){$Ids=Get-Content -Raw $PidFile|ConvertFrom-Json;foreach($ProcessId in @($Ids.server,$Ids.worker)){$p=Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue;if($p -and $p.ExecutablePath -eq $Ids.python -and $p.CommandLine -match 'backend.app'){Stop-Process -Id $ProcessId -ErrorAction SilentlyContinue}};Remove-Item -LiteralPath $PidFile}
