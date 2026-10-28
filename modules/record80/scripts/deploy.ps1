# Deploy only the verified recording module into a persistent board directory.
# Windows paths are limited to D:\study\LicheeRV.
param(
    [string]$BoardIp = '10.133.125.1'
)
$ErrorActionPreference = 'Stop'
$module = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$binary = Join-Path $module 'bin\camera_36record'
$supervisor = Join-Path $PSScriptRoot 'run_board.sh'
$config = Join-Path $module 'config\record80.yaml'
$boardReadme = Join-Path $module 'docs\BOARD_README.md'
$remote = 'root@' + $BoardIp
$remoteDir = '/code/camera/modules/record80'
$stage = $remoteDir + '/.deploy_' + [guid]::NewGuid().ToString('N')
if (!(Test-Path -LiteralPath $binary)) { throw "Compiled camera program missing: $binary. Run scripts\build.sh from WSL." }
if (!(Test-Path -LiteralPath $supervisor)) { throw 'Missing run_board.sh' }
if (!(Test-Path -LiteralPath $config)) { throw 'Missing record80.yaml' }
if (!(Test-Path -LiteralPath $boardReadme)) { throw 'Missing docs\BOARD_README.md' }
$hostHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $binary).Hash.ToLowerInvariant()
& ssh.exe -o BatchMode=yes -o ConnectTimeout=5 $remote 'if [ -d /code/camera/run/lock ] || pidof camera_36record >/dev/null 2>&1; then echo CAMERA_BUSY; exit 2; fi'
if ($LASTEXITCODE -ne 0) { throw 'Board camera busy or SSH unavailable: will not deploy.' }
$backup = $remoteDir + '/backup_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [guid]::NewGuid().ToString('N').Substring(0,8)
& ssh.exe -o BatchMode=yes $remote ('mkdir -p ' + $stage)
if ($LASTEXITCODE -ne 0) { throw 'Cannot create board staging directory.' }
& scp.exe -q -O $binary ($remote + ':' + $stage + '/camera_36record')
if ($LASTEXITCODE -ne 0) { throw 'Failed uploading camera binary.' }
& scp.exe -q -O $supervisor ($remote + ':' + $stage + '/run_board.sh')
if ($LASTEXITCODE -ne 0) { throw 'Failed uploading supervisor.' }
& scp.exe -q -O $config ($remote + ':' + $stage + '/record80.yaml')
if ($LASTEXITCODE -ne 0) { throw 'Failed uploading config.' }
& scp.exe -q -O $boardReadme ($remote + ':' + $stage + '/README.md')
if ($LASTEXITCODE -ne 0) { throw 'Failed uploading board README.' }
$hashOut = & ssh.exe -o BatchMode=yes $remote ('sh -n ' + $stage + '/run_board.sh && RECORD80_CONFIG=' + $stage + '/record80.yaml sh ' + $stage + '/run_board.sh --check-config && sha256sum ' + $stage + '/camera_36record')
if ($LASTEXITCODE -ne 0) { throw "Staged verification failed; old deployment unchanged. Stage: $stage" }
$boardHash = (($hashOut | Select-Object -Last 1).Trim() -split '\s+')[0].ToLowerInvariant()
if ($boardHash -ne $hostHash) { throw "Binary SHA256 mismatch: local $hostHash vs board $boardHash; old deployment unchanged" }
$install = 'set -e; if [ -d /code/camera/run/lock ] || pidof camera_36record >/dev/null 2>&1; then echo CAMERA_BUSY; exit 2; fi; mkdir -p ' + $remoteDir + '/config ' + $backup + '; for f in camera_36record run_board.sh; do if [ -e ' + $remoteDir + '/$f ]; then cp -p ' + $remoteDir + '/$f ' + $backup + '/$f; fi; done; if [ -e ' + $remoteDir + '/config/record80.yaml ]; then cp -p ' + $remoteDir + '/config/record80.yaml ' + $backup + '/record80.yaml; fi; cp ' + $stage + '/camera_36record ' + $remoteDir + '/camera_36record; cp ' + $stage + '/run_board.sh ' + $remoteDir + '/run_board.sh; cp ' + $stage + '/record80.yaml ' + $remoteDir + '/config/record80.yaml; chmod 755 ' + $remoteDir + '/camera_36record; sh -n ' + $remoteDir + '/run_board.sh; sh ' + $remoteDir + '/run_board.sh --check-config; sha256sum ' + $remoteDir + '/camera_36record'
$hashOut = & ssh.exe -o BatchMode=yes $remote $install
if ($LASTEXITCODE -ne 0) { throw "Install or verification failed. Inspect and restore from $backup; stage: $stage" }
$boardHash = (($hashOut | Select-Object -Last 1).Trim() -split '\s+')[0].ToLowerInvariant()
if ($boardHash -ne $hostHash) { throw "Installed SHA256 mismatch. Restore from $backup" }
$readmeHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $boardReadme).Hash.ToLowerInvariant()
$installReadme = 'set -e; test -s ' + $stage + '/README.md; if [ -e ' + $remoteDir + '/README.md ]; then cp -p ' + $remoteDir + '/README.md ' + $backup + '/README.md; fi; cp ' + $stage + '/README.md ' + $remoteDir + '/README.md; sha256sum ' + $remoteDir + '/README.md'
$readmeHashOut = & ssh.exe -o BatchMode=yes $remote $installReadme
if ($LASTEXITCODE -ne 0) { throw "Board README installation failed. Program deployment may already be complete; inspect $remoteDir and backup $backup" }
$installedReadmeHash = (($readmeHashOut | Select-Object -Last 1).Trim() -split '\s+')[0].ToLowerInvariant()
if ($installedReadmeHash -ne $readmeHash) { throw "Board README SHA256 mismatch. Inspect $remoteDir/README.md and backup $backup" }
Write-Host ('DEPLOY_PASS board=' + $BoardIp + ' SHA256=' + $hostHash) -ForegroundColor Green
Write-Host ('BACKUP=' + $backup)
Write-Host 'CONFIG: /code/camera/modules/record80/config/record80.yaml'
Write-Host 'BOARD README: /code/camera/modules/record80/README.md'
Write-Host 'BOARD CHECK: sh /code/camera/modules/record80/run_board.sh --check-config'
Write-Host 'BOARD START (YAML): sh /code/camera/modules/record80/run_board.sh'
Write-Host 'BOARD START (auto record): MAX_RUN_SEC=24 RECORD_TEST_AUTOSTART=1 sh /code/camera/modules/record80/run_board.sh'
Write-Host 'BOARD START (web buttons): MAX_RUN_SEC=300 sh /code/camera/modules/record80/run_board.sh'
Write-Host 'WEB (while running): http://10.133.124.1:8081/'
Write-Host 'RECORDINGS: /code/camera/recordings/*.avi'
