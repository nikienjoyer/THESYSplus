$ErrorActionPreference = 'Stop'
$backend = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pidFile = Join-Path $backend '.demo-run\backend.pid'
$waitress = Join-Path $backend 'venv\Scripts\waitress-serve.exe'
$python = Join-Path $backend 'venv\Scripts\python.exe'
$workerPidFile = Join-Path $backend '.demo-run\worker.pid'

if (-not (Test-Path -LiteralPath $pidFile)) { throw 'No demo backend PID file was found.' }
$demoPid = [int](Get-Content -LiteralPath $pidFile -Raw).Trim()
$all = @(Get-CimInstance Win32_Process)
$root = $all | Where-Object { $_.ProcessId -eq $demoPid } | Select-Object -First 1
if (-not $root) { throw 'The recorded demo backend process is no longer running.' }
if ($root.ExecutablePath -ne $waitress) {
    throw 'The recorded PID is no longer the expected Waitress executable; refusing to stop it.'
}
$chain = @($root)
for ($i = 0; $i -lt $chain.Count; $i++) {
    $children = @($all | Where-Object { $_.ParentProcessId -eq $chain[$i].ProcessId })
    foreach ($child in $children) {
        if ($child.ExecutablePath -like '*\conhost.exe') { continue }
        if ($child.CommandLine -notlike "*$waitress*") {
            throw "PID $($child.ProcessId) is not part of the expected Waitress launch chain. Refusing to stop any process."
        }
        $chain += $child
    }
}
for ($i = $chain.Count - 1; $i -ge 0; $i--) {
    Stop-Process -Id $chain[$i].ProcessId -ErrorAction SilentlyContinue
}
if (Test-Path -LiteralPath $workerPidFile) {
    $workerPid = [int](Get-Content -LiteralPath $workerPidFile -Raw).Trim()
    $worker = $all | Where-Object { $_.ProcessId -eq $workerPid } | Select-Object -First 1
    if ($worker) {
        if ($worker.ExecutablePath -ne $python -or $worker.CommandLine -notmatch 'manage\.py\s+process_jobs') {
            throw 'The recorded worker PID is not the THESYSplus processing worker; refusing to stop it.'
        }
        Stop-Process -Id $workerPid -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $workerPidFile
}
Remove-Item -LiteralPath $pidFile
$listenerFile = Join-Path $backend '.demo-run\backend.listener.pid'
if (Test-Path -LiteralPath $listenerFile) { Remove-Item -LiteralPath $listenerFile }
Write-Output "Stopped THESYSplus demo backend and processing worker."
