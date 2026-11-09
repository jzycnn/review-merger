param([Parameter(Mandatory=$true)][string]$BackupFile)
$ErrorActionPreference='Stop'
$Project=Split-Path $PSScriptRoot -Parent
$Config=Get-Content -Raw (Join-Path $Project 'installation.json')|ConvertFrom-Json
$env:REVIEW_HOME=$Config.DataRoot
& (Join-Path $PSScriptRoot 'stop.ps1')
& (Join-Path $Project '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'restore_month.py') $BackupFile
if($LASTEXITCODE){throw '恢复失败，请检查备份文件；服务保持停止状态'}
& (Join-Path $PSScriptRoot 'start.ps1')
