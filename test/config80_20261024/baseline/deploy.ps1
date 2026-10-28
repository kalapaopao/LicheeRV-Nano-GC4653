# Deploy only the verified recording module into a persistent board directory.
# Windows paths are limited to D:\study\LicheeRV.
param(
    [string]$BoardIp = '10.133.125.1'
)
$ErrorActionPreference = 'Stop'
$module = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$binary = Join-Path $module 'bin\camera_36record'
$supervisor = Join-Path $PSScriptRoot 'run_board.sh'
$remote = 'root@' + $BoardIp
$remoteDir = '/code/camera/modules/record80'
if (!(Test-Path -LiteralPath $binary)) { throw "Compiled camera program missing: $binary. Run scripts\build.sh from WSL." }
if (!(Test-Path -LiteralPath $supervisor)) { throw 'Missing run_board.sh' }
$hostHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $binary).Hash.ToLowerInvariant()
& ssh.exe -o BatchMode=yes -o ConnectTimeout=5 $remote 'if [ -d /code/camera/run/lock ] || pidof camera_36record >/dev/null 2>&1; then echo CAMERA_BUSY; exit 2; fi'
if ($LASTEXITCODE -ne 0) { throw 'Board camera busy or SSH unavailable: will not deploy.' }
& ssh.exe -o BatchMode=yes $remote ('mkdir -p ' + $remoteDir)
if ($LASTEXITCODE -ne 0) { throw 'Cannot create board module directory.' }
& scp.exe -q -O $binary ($remote + ':' + $remoteDir + '/camera_36record')
if ($LASTEXITCODE -ne 0) { throw 'Failed uploading camera binary.' }
& scp.exe -q -O $supervisor ($remote + ':' + $remoteDir + '/run_board.sh')
if ($LASTEXITCODE -ne 0) { throw 'Failed uploading supervisor.' }
$hashOut = & ssh.exe -o BatchMode=yes $remote ('chmod 755 ' + $remoteDir + '/camera_36record; sh -n ' + $remoteDir + '/run_board.sh && sha256sum ' + $remoteDir + '/camera_36record')
if ($LASTEXITCODE -ne 0) { throw 'Board program or supervisor verification failed.' }
$boardHash = (($hashOut | Select-Object -Last 1).Trim() -split '\s+')[0].ToLowerInvariant()
if ($boardHash -ne $hostHash) { throw "Binary SHA256 mismatch: local $hostHash vs board $boardHash" }
Write-Host ('DEPLOY_PASS board=' + $BoardIp + ' SHA256=' + $hostHash) -ForegroundColor Green
Write-Host 'BOARD START (auto record): MAX_RUN_SEC=24 RECORD_TEST_AUTOSTART=1 sh /code/camera/modules/record80/run_board.sh'
Write-Host 'BOARD START (web buttons): MAX_RUN_SEC=300 sh /code/camera/modules/record80/run_board.sh'
Write-Host 'WEB (while running): http://10.133.124.1:8081/'
Write-Host 'RECORDINGS: /code/camera/recordings/*.avi'
