$ErrorActionPreference='Stop'
$dir=Split-Path -Parent $MyInvocation.MyCommand.Path
$log=Join-Path $dir 'web_control_test.log'
$err=Join-Path $dir 'web_control_test_error.log'
$hostIP='10.133.124.1'
$base='http://10.133.124.1:8082'
$temp=(& ssh.exe -o BatchMode=yes "root@$hostIP" 'cat /sys/class/thermal/thermal_zone0/temp' | Select-Object -Last 1).Trim()
Write-Host "INITIAL_TEMP_MC=$temp"
if([int]$temp -ge 70000){ throw 'Board is too hot for a new supervised session' }
$ssh=Start-Process -FilePath 'ssh.exe' -ArgumentList @('-o','BatchMode=yes',"root@$hostIP",'MAX_RUN_SEC=24 sh /tmp/clock36_record_20261024/record36_supervisor.sh') -PassThru -RedirectStandardOutput $log -RedirectStandardError $err -WindowStyle Hidden
try{
    $ready=$false
    for($i=0;$i -lt 19;$i++){
        Start-Sleep -Seconds 1
        if($ssh.HasExited){throw "Supervisor exited during startup: $($ssh.ExitCode)"}
        try {
            $status=Invoke-RestMethod -Uri "$base/status" -TimeoutSec 2
            $ready=$true;break
        }catch{}
    }
    if(!$ready){ throw 'Control API not ready within startup window' }
    Write-Host ('READY='+($status|ConvertTo-Json -Compress))
    $page=& curl.exe --silent --show-error --max-time 4 -o NUL -w '%{http_code}' ('http://'+$hostIP+':8081/')
    Write-Host "PAGE_HTTP=$page"
    if($page -ne '200'){throw 'Page HTTP was not 200'}
    $start=Invoke-RestMethod -Uri "$base/start" -Method POST -TimeoutSec 3
    Write-Host ('POST_START='+($start|ConvertTo-Json -Compress))
    Start-Sleep -Seconds 5
    $during=Invoke-RestMethod -Uri "$base/status" -TimeoutSec 3
    Write-Host ('DURING='+($during|ConvertTo-Json -Compress))
    if(!($during.written -gt 0)){throw 'Recording did not write any frames'}
    $stop=Invoke-RestMethod -Uri "$base/stop" -Method POST -TimeoutSec 3
    Write-Host ('POST_STOP='+($stop|ConvertTo-Json -Compress))
    Start-Sleep -Seconds 2
    $after=Invoke-RestMethod -Uri "$base/status" -TimeoutSec 3
    Write-Host ('AFTER='+($after|ConvertTo-Json -Compress))
    if($after.recording -or !$after.last){throw 'Recording did not finish a file'}
    Write-Host 'WEB_CONTROL_TEST_PASS'
}finally{
    $ssh.WaitForExit(40000)|Out-Null
    Write-Host "SUPERVISOR_EXIT=$($ssh.ExitCode)"
    Get-Content -LiteralPath $log -Tail 8 -ErrorAction SilentlyContinue
    Get-Content -LiteralPath $err -Tail 8 -ErrorAction SilentlyContinue
}
