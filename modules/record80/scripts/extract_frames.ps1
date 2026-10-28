# Extract YOLO annotation frames from a completed AVI, within the project only.
param(
    [Parameter(Mandatory=$true)][string]$Video,
    [ValidateRange(1,30)][int]$ExtractFps=5,
    [string]$FFmpegExe='ffmpeg.exe'
)
$ErrorActionPreference='Stop'
$binary=Get-Command $FFmpegExe -ErrorAction SilentlyContinue
if(!$binary){throw 'FFmpeg not found; specify -FFmpegExe with an existing executable path.'}
$inputPath=(Resolve-Path -LiteralPath $Video).Path
if([IO.Path]::GetExtension($inputPath).ToLowerInvariant() -ne '.avi'){throw 'Input must be a finalized .avi file'}
$module=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$stem=[IO.Path]::GetFileNameWithoutExtension($inputPath)
$dst=Join-Path $module ('dataset_frames\'+$stem)
New-Item -ItemType Directory -Path $dst -Force | Out-Null
$out=Join-Path $dst 'frame_%06d.jpg'
& $binary.Source -hide_banner -loglevel warning -i $inputPath -vf "fps=$ExtractFps" -q:v 2 $out
if($LASTEXITCODE -ne 0){throw 'FFmpeg frame extraction failed'}
$count=@(Get-ChildItem -LiteralPath $dst -File -Filter 'frame_*.jpg').Count
Write-Host ('EXTRACTED '+$count+' frames to '+$dst) -ForegroundColor Green
