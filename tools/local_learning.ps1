param([ValidateSet('Install', 'Start', 'Stop', 'RestartBackend', 'RestartFrontend', 'Status')][string]$Action = 'Status')
$ErrorActionPreference = 'Stop'
$demoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$demoPython = Join-Path $demoRoot 'backend\.venv\Scripts\pythonw.exe'
$demoLauncher = Join-Path $PSScriptRoot 'local_learning_process.py'
$demoRoles = @('backend', 'frontend')
function TaskName([string]$Role) { return "DataPact-Learning-$Role-20261024" }
function AssertOwned([string]$Role) {
    $task = Get-ScheduledTask -TaskName (TaskName $Role) -ErrorAction SilentlyContinue
    if ($task -and ($task.Actions.Execute -ne $demoPython -or $task.Actions.Arguments -ne "`"$demoLauncher`" $Role")) {
        throw "Task name belongs to a different launcher: $(TaskName $Role)"
    }
    return $task
}
foreach ($role in $demoRoles) { $null = AssertOwned $role }
if ($Action -eq 'Install') {
    & (Join-Path $demoRoot 'backend\.venv\Scripts\python.exe') $demoLauncher prepare
    if ($LASTEXITCODE -ne 0) { throw 'Demo configuration preparation failed' }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    foreach ($role in $demoRoles) {
        if (-not (AssertOwned $role)) {
            $taskAction = New-ScheduledTaskAction -Execute $demoPython -Argument "`"$demoLauncher`" $role" -WorkingDirectory $demoRoot
            Register-ScheduledTask -TaskName (TaskName $role) -Action $taskAction -Settings $settings -Principal $principal -Description 'Controlled local DataPact learning demo; loopback, mock payments, no paid models.' | Out-Null
        }
    }
}
if ($Action -eq 'Stop' -or $Action -in @('RestartBackend', 'RestartFrontend')) {
    $restartRole = if ($Action -eq 'RestartFrontend') { 'frontend' } else { 'backend' }
    $restartPort = if ($restartRole -eq 'frontend') { 3026 } else { 8026 }
    $roles = if ($Action -ne 'Stop') { @($restartRole) } else { $demoRoles }
    foreach ($role in $roles) { Stop-ScheduledTask -TaskName (TaskName $role) }
    if ($Action -ne 'Stop') {
        for ($attempt = 0; $attempt -lt 40; $attempt++) {
            if (-not (Get-NetTCPConnection -State Listen -LocalPort $restartPort -ErrorAction SilentlyContinue)) { break }
            Start-Sleep -Milliseconds 250
        }
        if (Get-NetTCPConnection -State Listen -LocalPort $restartPort -ErrorAction SilentlyContinue) { throw 'Owned service did not stop; refusing a second listener' }
        Start-ScheduledTask -TaskName (TaskName $restartRole)
    }
}
if ($Action -eq 'Start') {
    foreach ($role in $demoRoles) {
        $task = AssertOwned $role
        if (-not $task) { throw 'Install the project-owned tasks first' }
        $port = if ($role -eq 'backend') { 8026 } else { 3026 }
        if ($task.State -ne 'Running' -and (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)) { throw "Port $port is owned by another process" }
        Start-ScheduledTask -TaskName (TaskName $role)
    }
}
foreach ($role in $demoRoles) {
    $task = AssertOwned $role
    if ($task) {
        $info = Get-ScheduledTaskInfo -TaskName $task.TaskName
        [pscustomobject]@{Task=$task.TaskName;State=$task.State;LastResult=$info.LastTaskResult;Root=$demoRoot}
    }
}
