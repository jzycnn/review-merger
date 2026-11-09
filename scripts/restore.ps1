param([Parameter(Mandatory=$true)][string]$BackupFile)
$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'stop.ps1')
$Project=Split-Path $PSScriptRoot -Parent
$Config=Get-Content -Raw (Join-Path $Project 'installation.json')|ConvertFrom-Json
$env:REVIEW_HOME=$Config.DataRoot
& (Join-Path $Project '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'restore.py') $BackupFile
if($LASTEXITCODE){throw '恢复失败，原数据保留'}
& (Join-Path $PSScriptRoot 'start.ps1')
