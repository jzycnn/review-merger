param([string]$DataRoot = '')
$ErrorActionPreference = 'Stop'
$Project = Split-Path $PSScriptRoot -Parent
if (!$DataRoot) { if (Test-Path 'D:\') {$DataRoot='D:\审片意见整理系统'} else {$DataRoot=Join-Path $env:LOCALAPPDATA 'ReviewMerger'} }
$DataRoot=[IO.Path]::GetFullPath($DataRoot)
New-Item -ItemType Directory -Force $DataRoot | Out-Null
$PythonCommand=Get-Command python -ErrorAction SilentlyContinue
if (!$PythonCommand) { $Bundled=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'; if(Test-Path $Bundled){$PythonCommand=[pscustomobject]@{Source=$Bundled}}else{throw '请先安装Python 3.12，并加入PATH。'} }
& $PythonCommand.Source -m venv (Join-Path $Project '.venv')
if ($LASTEXITCODE) {throw '创建Python环境失败'}
$Python=Join-Path $Project '.venv\Scripts\python.exe'
& $Python -m pip install -r (Join-Path $Project 'requirements.txt')
if ($LASTEXITCODE) {throw '安装依赖失败'}
Push-Location (Join-Path $Project 'frontend')
try { & npm.cmd ci --no-audit --no-fund; if($LASTEXITCODE){throw '前端依赖安装失败'}; & npm.cmd run build; if($LASTEXITCODE){throw '前端构建失败'} } finally {Pop-Location}
@{DataRoot=$DataRoot} | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $Project 'installation.json')
$env:REVIEW_HOME=$DataRoot
Push-Location $Project
try {& $Python -c 'import backend.app.core';if($LASTEXITCODE){throw '数据库初始化失败'}} finally {Pop-Location}
$Action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+(Join-Path $PSScriptRoot 'start.ps1')+'"') -WorkingDirectory $Project
$Trigger=New-ScheduledTaskTrigger -AtLogOn -User ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
$Principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$Settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'ReviewMerger-Local' -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force | Out-Null
& (Join-Path $PSScriptRoot 'start.ps1')
Start-Process 'http://127.0.0.1:8765'
