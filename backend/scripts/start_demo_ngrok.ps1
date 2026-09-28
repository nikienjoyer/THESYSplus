$ErrorActionPreference = 'Stop'
$backend = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $backend '.demo-run'
$ngrok = (Get-Command ngrok -ErrorAction Stop).Source

$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -eq '127.0.0.1' } | Select-Object -First 1
if (-not $listener) { throw 'The secure backend is not listening on 127.0.0.1:8000.' }
$owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
if ($owner.CommandLine -notlike '*waitress-serve.exe*') {
    throw 'Port 8000 is not owned by the expected Waitress demo server.'
}
$health = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/health' -UseBasicParsing -TimeoutSec 10
if ($health.StatusCode -ne 200 -or $health.Content -notmatch '"status":\s*"ok"') {
    throw 'The local THESYSplus health check did not pass.'
}
$unknown = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/definitely-not-a-route' -UseBasicParsing -SkipHttpErrorCheck -TimeoutSec 10
if ($unknown.Content -match 'DEBUG = True') { throw 'Django debug pages are still enabled.' }
$mediaRoot = Join-Path $backend 'media'
$file = Get-ChildItem (Join-Path $mediaRoot 'theses') -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if ($file) {
    $relative = [System.IO.Path]::GetRelativePath($mediaRoot, $file.FullName).Replace([char]92, [char]47)
    $direct = Invoke-WebRequest -Uri "http://127.0.0.1:8000/media/$relative" -Method Head -UseBasicParsing -SkipHttpErrorCheck -TimeoutSec 10
    if ($direct.StatusCode -ne 404) { throw 'A stored thesis remains directly accessible through /media/.' }
}

New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$pidFile = Join-Path $runtime 'ngrok.pid'
if (Test-Path -LiteralPath $pidFile) { throw 'An ngrok PID file already exists. Check the existing endpoint first.' }
$agent = Start-Process -FilePath $ngrok -ArgumentList @('http', '8000') `
    -WorkingDirectory $backend -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $runtime 'ngrok.stdout.log') `
    -RedirectStandardError (Join-Path $runtime 'ngrok.stderr.log')
Set-Content -LiteralPath $pidFile -Value $agent.Id

$publicUrl = $null
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Seconds 1
    try {
        $tunnels = Invoke-RestMethod -Uri 'http://127.0.0.1:4040/api/tunnels' -TimeoutSec 2
        $publicUrl = $tunnels.tunnels | Where-Object { $_.public_url -like 'https://*' } |
            Select-Object -ExpandProperty public_url -First 1
        if ($publicUrl) { break }
    } catch { }
    if ($agent.HasExited) { break }
}
if (-not $publicUrl) {
    throw "ngrok did not report an HTTPS endpoint. Check its local logs in $runtime."
}
Set-Content -LiteralPath (Join-Path $runtime 'ngrok-url.txt') -Value $publicUrl
Write-Output "ngrok endpoint: $publicUrl"
Write-Output "ngrok launcher PID $($agent.Id); PID, URL, and logs: $runtime"
