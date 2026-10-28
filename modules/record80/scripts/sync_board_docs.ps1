# Synchronize documentation only; never deploy the camera binary or YAML.
param(
    [ValidatePattern('^[0-9]{1,3}(\.[0-9]{1,3}){3}$')]
    [string]$BoardIp = '10.133.125.1',
    [ValidatePattern('^[A-Za-z0-9._-]*$')]
    [string]$HostKeyAlias = ''
)
$ErrorActionPreference = 'Stop'
if ([System.Net.IPAddress]::Parse($BoardIp).AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { throw 'IPv4 address required' }
$module = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$project = (Resolve-Path (Join-Path $module '..\..')).Path
$remote = 'root@' + $BoardIp
$sshOptions = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5')
if ($HostKeyAlias) { $sshOptions += @('-o', ('HostKeyAlias=' + $HostKeyAlias)) }
$tag = (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [guid]::NewGuid().ToString('N').Substring(0,8)
$stage = '/code/camera/.docs_stage_' + $tag
$backup = '/code/camera/backup_docs_' + $tag
$items = @(
    @{Source=(Join-Path $module 'docs\BOARD_README.md'); Name='root_README.md'; Target='/code/camera/README.md'},
    @{Source=(Join-Path $module 'docs\BOARD_README.md'); Name='module_README.md'; Target='/code/camera/modules/record80/README.md'},
    @{Source=(Join-Path $module 'docs\CONFIG.md'); Name='CONFIG.md'; Target='/code/camera/modules/record80/docs/CONFIG.md'},
    @{Source=(Join-Path $project 'docs\WIFI_CONNECTION.md'); Name='WIFI_CONNECTION.md'; Target='/code/camera/docs/WIFI_CONNECTION.md'}
)
# Inspect every source and destination before installing anything.
foreach ($item in $items) {
    if (!(Test-Path -LiteralPath $item.Source -PathType Leaf)) { throw ('Missing documentation: ' + $item.Source) }
    $item.Hash = (Get-FileHash -LiteralPath $item.Source -Algorithm SHA256).Hash.ToLowerInvariant()
    $inspect = 'set -e; test ! -L ' + $item.Target + '; if [ -e ' + $item.Target + ' ]; then sha256sum ' + $item.Target + '; else echo ABSENT; fi'
    $out = & ssh.exe @sshOptions $remote $inspect
    if ($LASTEXITCODE -ne 0) { throw ('Cannot inspect board document: ' + $item.Target) }
    $item.OldHash = (($out | Select-Object -Last 1).Trim() -split '\s+')[0]
    if ($item.OldHash -ne 'ABSENT' -and $item.OldHash -notmatch '^[a-fA-F0-9]{64}$') { throw 'Invalid remote checksum' }
}
& ssh.exe @sshOptions $remote ('test ! -e ' + $stage + ' && mkdir ' + $stage)
if ($LASTEXITCODE -ne 0) { throw 'Cannot create document staging directory' }
foreach ($item in $items) {
    & scp.exe -q -O @sshOptions $item.Source ($remote + ':' + $stage + '/' + $item.Name)
    if ($LASTEXITCODE -ne 0) { throw ('Document upload failed; old documents unchanged. Stage: ' + $stage) }
}
$commands = @('set -e', ('test ! -e ' + $backup))
# Verify all candidates and unchanged destinations before replacing any document.
foreach ($item in $items) {
    $commands += ('test ! -L ' + $item.Target)
    $commands += ('test -s ' + $stage + '/' + $item.Name)
    $commands += ('test "$(sha256sum ' + $stage + '/' + $item.Name + ' | cut -d '' '' -f 1)" = ' + $item.Hash)
    if ($item.OldHash -eq 'ABSENT') { $commands += ('test ! -e ' + $item.Target) }
    else { $commands += ('test "$(sha256sum ' + $item.Target + ' | cut -d '' '' -f 1)" = ' + $item.OldHash) }
}
$commands += ('mkdir ' + $backup)
$commands += ('sha256sum /code/camera/modules/record80/camera_36record /code/camera/modules/record80/run_board.sh /code/camera/modules/record80/config/record80.yaml > ' + $backup + '/protected.sha256')
foreach ($item in $items) {
    if ($item.OldHash -ne 'ABSENT') { $commands += ('cp -p ' + $item.Target + ' ' + $backup + '/' + $item.Name) }
    else { $commands += ('touch ' + $backup + '/' + $item.Name + '.absent') }
}
$commands += 'mkdir -p /code/camera/modules/record80/docs /code/camera/docs'
foreach ($item in $items) {
    $commands += ('cp ' + $stage + '/' + $item.Name + ' ' + $item.Target)
    $commands += ('test "$(sha256sum ' + $item.Target + ' | cut -d '' '' -f 1)" = ' + $item.Hash)
    $commands += ('sha256sum ' + $item.Target)
}
$commands += ('sha256sum -c ' + $backup + '/protected.sha256')
$result = & ssh.exe @sshOptions $remote ($commands -join '; ')
if ($LASTEXITCODE -ne 0) { throw "Document synchronization failed; some documents may already be updated. Inspect backup $backup and stage $stage. Program and YAML were not uploaded." }
$result | Write-Host
Write-Host ('DOC_SYNC_PASS board=' + $BoardIp) -ForegroundColor Green
Write-Host ('DOC_BACKUP=' + $backup)
Write-Host ('DOC_STAGE=' + $stage)
Write-Host 'README: /code/camera/README.md and /code/camera/modules/record80/README.md'
Write-Host 'PROGRAM/YAML/STARTUP: unchanged (checksums verified)'
