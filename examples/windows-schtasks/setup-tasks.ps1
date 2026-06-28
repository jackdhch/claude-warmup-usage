<#
  Registers two Windows scheduled tasks that drive the warmup script inside WSL:
    ClaudeWarmup_Morning : weekdays at $MorningTime, proactive `run` (wakes the PC)
    ClaudeWarmup_Auto    : every day, hourly 09:00-24:00, `run --auto`
  Run from a normal PowerShell (no admin needed for InteractiveToken).

  Edit the variables below to match your WSL distro and where you cloned the repo.
#>

# --- EDIT THESE ---------------------------------------------------------------
$Distro      = "Ubuntu"
$RepoWslPath = "/home/$(wsl.exe -d $Distro -e bash -lc 'echo $USER')/claude-warmup-usage"
$MorningTime = "06:55"          # weekday proactive warmup
# ------------------------------------------------------------------------------

$Python = "$RepoWslPath/.venv/bin/python"
$Script = "$RepoWslPath/claude_warmup_usage.py"
$Sid    = (New-Object System.Security.Principal.NTAccount($env:USERNAME)
          ).Translate([System.Security.Principal.SecurityIdentifier]).Value
$Wsl    = "C:\Windows\System32\wsl.exe"
$Tomorrow = (Get-Date).AddDays(1).ToString("yyyy-MM-dd")

function New-WarmupTask($Name, $Args, $TriggerXml, $Wake) {
  # Launch wsl via a hidden VBScript so no console window flashes on each run.
  $vbs = "code = CreateObject(""WScript.Shell"").Run(""$Wsl -d $Distro -e bash -lc """"$Python $Script $Args"""""", 0, True)`r`nWScript.Quit(code)"
  $vbsPath = "$env:USERPROFILE\$Name.vbs"
  Set-Content -Path $vbsPath -Value $vbs -Encoding ASCII
  $xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Author>$env:USERNAME</Author></RegistrationInfo>
  <Triggers>$TriggerXml</Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$Sid</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>$($Wake.ToString().ToLower())</WakeToRun>
    <ExecutionTimeLimit>PT15M</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>C:\Windows\System32\wscript.exe</Command>
      <Arguments>$vbsPath</Arguments>
    </Exec>
  </Actions>
</Task>
"@
  $tmp = "$env:TEMP\$Name.xml"
  Set-Content -Path $tmp -Value $xml -Encoding Unicode
  schtasks.exe /Create /TN $Name /XML $tmp /F
}

$morningTrigger = @"
<CalendarTrigger>
  <StartBoundary>${Tomorrow}T$MorningTime`:00</StartBoundary>
  <Enabled>true</Enabled>
  <ScheduleByWeek>
    <DaysOfWeek><Monday/><Tuesday/><Wednesday/><Thursday/><Friday/></DaysOfWeek>
    <WeeksInterval>1</WeeksInterval>
  </ScheduleByWeek>
</CalendarTrigger>
"@

$autoTrigger = @"
<CalendarTrigger>
  <StartBoundary>${Tomorrow}T09:00:00</StartBoundary>
  <Enabled>true</Enabled>
  <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
  <Repetition><Interval>PT1H</Interval><Duration>PT15H</Duration><StopAtDurationEnd>true</StopAtDurationEnd></Repetition>
</CalendarTrigger>
"@

New-WarmupTask "ClaudeWarmup_Morning" "run"        $morningTrigger $true
New-WarmupTask "ClaudeWarmup_Auto"    "run --auto" $autoTrigger    $false

Write-Output "Done. Verify with: schtasks /Query /TN ClaudeWarmup_Morning /V /FO LIST"
Write-Output "Test now with:    schtasks /Run /TN ClaudeWarmup_Auto"
