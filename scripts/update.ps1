$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'stop.ps1')
$Project=Split-Path $PSScriptRoot -Parent
$Config=Get-Content -Raw (Join-Path $Project 'installation.json')|ConvertFrom-Json
& (Join-Path $PSScriptRoot 'install.ps1') -DataRoot $Config.DataRoot
