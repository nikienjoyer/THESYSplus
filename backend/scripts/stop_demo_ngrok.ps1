$ErrorActionPreference = 'Stop'
$backend = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $backend '.demo-run'
$pidFile = Join-Path $runtime 'ngrok.pid'

if (-not (Test-Path -LiteralPath $pidFile)) { throw 'No demo ngrok PID file was found.' }
$demoPid = [int](Get-Content -LiteralPath $pidFile -Raw).Trim()
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$demoPid"
if (-not $process) { throw 'The recorded ngrok process is no longer running.' }
$expected = (Get-Command ngrok -ErrorAction Stop).Source
if ($process.ExecutablePath -ne $expected -or $process.CommandLine -notmatch '\bhttp 8000\b') {
    throw 'The recorded PID is no longer the expected ngrok demo process; refusing to stop it.'
}
Stop-Process -Id $demoPid -ErrorAction Stop
Remove-Item -LiteralPath $pidFile
$urlFile = Join-Path $runtime 'ngrok-url.txt'
if (Test-Path -LiteralPath $urlFile) { Remove-Item -LiteralPath $urlFile }
Write-Output "Stopped THESYSplus demo ngrok process PID $demoPid."
