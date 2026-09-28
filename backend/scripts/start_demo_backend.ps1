param(
    [string]$NgrokHost = ''
)

$ErrorActionPreference = 'Stop'
$backend = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $backend 'venv\Scripts\python.exe'
$waitress = Join-Path $backend 'venv\Scripts\waitress-serve.exe'
$secrets = Join-Path $backend '.env.demo'
$runtime = Join-Path $backend '.demo-run'

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $waitress)) {
    throw 'The backend virtual environment needs Waitress installed.'
}
if (-not (Test-Path -LiteralPath $secrets)) {
    throw 'Missing ignored backend/.env.demo with DJANGO_SECRET_KEY and JWT_SECRET.'
}
if ($NgrokHost -and ($NgrokHost -notmatch '^[a-z0-9][a-z0-9.-]*[a-z0-9]$' -or $NgrokHost.Contains('..'))) {
    throw 'NgrokHost must be a hostname only, without https:// or a path.'
}
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 8000 is already in use. Stop the existing THESYSplus server first.'
}

foreach ($line in Get-Content -LiteralPath $secrets) {
    if ($line -match '^(DJANGO_SECRET_KEY|JWT_SECRET)=(.+)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
    }
}
if ($env:DJANGO_SECRET_KEY.Length -lt 50 -or $env:JWT_SECRET.Length -lt 50) {
    throw 'Demo secrets must each contain at least 50 characters.'
}

$env:DJANGO_ENV = 'production'
$env:FRONTEND_ORIGIN = 'https://thesysplus.vercel.app'
$env:FRONTEND_BASE_URL = 'https://thesysplus.vercel.app'
$env:DJANGO_ALLOWED_HOSTS = '127.0.0.1,localhost'
$env:DJANGO_CSRF_TRUSTED_ORIGINS = 'https://thesysplus.vercel.app'
if ($NgrokHost) {
    $env:DJANGO_ALLOWED_HOSTS += ",$NgrokHost"
    $env:DJANGO_CSRF_TRUSTED_ORIGINS += ",https://$NgrokHost"
}

New-Item -ItemType Directory -Path $runtime -Force | Out-Null
Push-Location $backend
try {
    & $python manage.py collectstatic --noinput --verbosity 0
    if ($LASTEXITCODE -ne 0) { throw 'collectstatic failed.' }

    $process = Start-Process -FilePath $waitress `
        -ArgumentList @('--listen=127.0.0.1:8000', '--threads=2', '--no-clear-untrusted-proxy-headers', 'thesys.demo_wsgi:application') `
        -WorkingDirectory $backend -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtime 'backend.stdout.log') `
        -RedirectStandardError (Join-Path $runtime 'backend.stderr.log')
    Set-Content -LiteralPath (Join-Path $runtime 'backend.pid') -Value $process.Id
    Start-Sleep -Seconds 2
    if ($process.HasExited) { throw "Waitress exited. See $runtime for diagnostics." }
    $health = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/health' -UseBasicParsing -TimeoutSec 10
    if ($health.StatusCode -ne 200 -or $health.Content -notmatch '"status":\s*"ok"') {
        throw "Unexpected health response. See $runtime for diagnostics."
    }
    $listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction Stop |
        Where-Object { $_.LocalAddress -eq '127.0.0.1' } |
        Select-Object -First 1
    if (-not $listener) { throw 'The demo backend is not bound to loopback only.' }
    Set-Content -LiteralPath (Join-Path $runtime 'backend.listener.pid') -Value $listener.OwningProcess
    Write-Output "THESYSplus demo backend running on 127.0.0.1:8000 (launcher PID $($process.Id), listener PID $($listener.OwningProcess))."
    Write-Output "Logs and PID: $runtime"
} finally {
    Pop-Location
}
