# Read-only pixel statistics. No image conversion or modification.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$root = Join-Path $PSScriptRoot 'session_23253_3371'
foreach ($name in @('first-hw.jpg', 'after-hw.jpg', 'late-hw.jpg')) {
    $bmp = [Drawing.Bitmap]::new((Join-Path $root $name))
    try {
        [double]$r=0; [double]$g=0; [double]$b=0; [long]$n=0
        for ($y=0; $y -lt $bmp.Height; $y+=4) {
            for ($x=0; $x -lt $bmp.Width; $x+=4) {
                $c=$bmp.GetPixel($x,$y)
                $luma=0.299*$c.R+0.587*$c.G+0.114*$c.B
                if ($luma -lt 32) { $r+=$c.R; $g+=$c.G; $b+=$c.B; $n++ }
            }
        }
        [pscustomobject]@{file=$name; criterion='decoded JPEG luma < 32, grid step 4'; samples=$n; mean_r=[math]::Round($r/$n,3); mean_g=[math]::Round($g/$n,3); mean_b=[math]::Round($b/$n,3)} | ConvertTo-Json -Compress
    } finally { $bmp.Dispose() }
}
# First VI frame is NV21: one Y plane followed by interleaved V,U.
$raw=[IO.File]::ReadAllBytes((Join-Path $root 'first-raw.nv21'))
$w=1280; $h=720; $offset=$w*$h
if($raw.Length -ne ($offset*3/2)){throw 'Unexpected NV21 size'}
[double]$vs=0; [double]$us=0; [double]$ys=0; [long]$n=0
for($y=0;$y -lt $h;$y+=4){
    for($x=0;$x -lt $w;$x+=4){
        $vY=$raw[$y*$w+$x]
        if($vY -lt 32){
            $i=$offset+[int]($y/2)*$w+$x
            $ys+=$vY; $vs+=$raw[$i]; $us+=$raw[$i+1]; $n++
        }
    }
}
[pscustomobject]@{file='first-raw.nv21'; criterion='VI Y < 32, grid step 4'; samples=$n; mean_y=[math]::Round($ys/$n,3); mean_v=[math]::Round($vs/$n,3); mean_u=[math]::Round($us/$n,3); chroma_neutral=128} | ConvertTo-Json -Compress
# These are scene statistics, not a black-level or white-balance calibration.
