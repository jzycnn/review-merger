& (Join-Path $PSScriptRoot 'stop.ps1')
Unregister-ScheduledTask -TaskName 'ReviewMerger-Local' -Confirm:$false -ErrorAction SilentlyContinue
Write-Host '已取消自动启动，保留全部数据、源代码及Windows中保存的API凭据。'
