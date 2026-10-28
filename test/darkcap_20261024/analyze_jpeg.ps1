$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
Get-ChildItem (Join-Path $PSScriptRoot 'results') -Directory | ForEach-Object {
    $path=Join-Path $_.FullName 'after-hw.jpg'
    if(!(Test-Path -LiteralPath $path)){return}
    $bmp=[Drawing.Bitmap]::new($path)
    try{
        [double]$r=0;[double]$g=0;[double]$b=0;[long]$n=0
        for($y=16;$y -lt $bmp.Height-16;$y+=4){
            for($x=16;$x -lt $bmp.Width-16;$x+=4){
                $c=$bmp.GetPixel($x,$y);$r+=$c.R;$g+=$c.G;$b+=$c.B;$n++
            }
        }
        [pscustomobject]@{session=$_.Name;samples=$n;mean_r=[math]::Round($r/$n,5);mean_g=[math]::Round($g/$n,5);mean_b=[math]::Round($b/$n,5);r_minus_g=[math]::Round(($r-$g)/$n,5);b_minus_g=[math]::Round(($b-$g)/$n,5)} | ConvertTo-Json -Compress
    }finally{$bmp.Dispose()}
}
