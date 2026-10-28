# Synchronize finalized AVI + JSON from board to this module's captures directory.
# Only writes within D:\study\LicheeRV\modules\record80\captures.
param(
  [string]$BoardIp='10.133.125.1',
  [string]$NamePattern='*'
)
$ErrorActionPreference = 'Stop'
$remote='root@'+$BoardIp
$module=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dest=Join-Path $module 'captures'
New-Item -ItemType Directory -Path $dest -Force | Out-Null
$files=@(& ssh.exe -o BatchMode=yes -o ConnectTimeout=5 $remote 'find /code/camera/recordings -maxdepth 1 -type f')
if ($LASTEXITCODE -ne 0) { throw 'SSH file listing failed' }
$added=0; $skipped=0
foreach($remotePath in $files){
  $name=($remotePath -split '/')[-1]
  if ($name -notmatch '^gc4653_[A-Za-z0-9_.-]+\.avi(\.json)?$'){continue}
  if ($name -notlike $NamePattern) { continue }
  $target=Join-Path $dest $name
  if (Test-Path -LiteralPath $target) { $skipped++; continue }
  $temp=$target+'.download'
  try{
    & scp.exe -q -O ($remote+':'+$remotePath) $temp
    if ($LASTEXITCODE -ne 0) {throw ('Download failed: '+$name)}
    if ((Get-Item -LiteralPath $temp).Length -eq 0) {throw ('Empty file: '+$name)}
    Move-Item -LiteralPath $temp -Destination $target
    $added++
    Write-Host ('DOWNLOADED '+$name)
  }finally{
    if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp -Force}
  }
}
Write-Host ('SYNC_DONE new='+$added+' existing='+$skipped+' destination='+$dest) -ForegroundColor Green
