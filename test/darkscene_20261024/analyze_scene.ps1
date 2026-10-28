$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
Get-ChildItem (Join-Path $PSScriptRoot 'results') -Directory | ForEach-Object {
    $image=Join-Path $_.FullName 'after-hw.jpg'
    if(!(Test-Path -LiteralPath $image)){return}
    $bmp=[Drawing.Bitmap]::new($image)
    try {
        [double]$r=0;[double]$g=0;[double]$b=0;[long]$n=0
        for($y=0;$y -lt $bmp.Height;$y+=4){
            for($x=0;$x -lt $bmp.Width;$x+=4){
                $c=$bmp.GetPixel($x,$y)
                if((0.299*$c.R+0.587*$c.G+0.114*$c.B) -lt 32){$r+=$c.R;$g+=$c.G;$b+=$c.B;$n++}
            }
        }
        [pscustomobject]@{session=$_.Name;criterion='JPEG luma<32 grid step4; scene statistic, not calibration';samples=$n;mean_r=[math]::Round($r/$n,3);mean_g=[math]::Round($g/$n,3);mean_b=[math]::Round($b/$n,3);r_minus_g=[math]::Round(($r-$g)/$n,3)} | ConvertTo-Json -Compress
    }finally{$bmp.Dispose()}
}
