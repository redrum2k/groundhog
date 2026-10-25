param(
    [ValidateSet('Install', 'Start', 'Stop', 'RestartBackend', 'RestartFrontend', 'Status')][string]$Action = 'Status',
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$')][string]$Instance = 'legacy',
    [ValidateRange(1024,65535)][int]$BackendPort = 8026,
    [ValidateRange(1024,65535)][int]$FrontendPort = 3026
)
$ErrorActionPreference = 'Stop'
if ($BackendPort -eq $FrontendPort) { throw 'Backend and frontend ports must differ' }
$demoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$demoPython = Join-Path $demoRoot 'backend\.venv\Scripts\pythonw.exe'
$demoLauncher = Join-Path $PSScriptRoot 'local_learning_process.py'
$demoRoles = @('backend', 'frontend')
function TaskName([string]$Role) {
    if ($Instance -eq 'legacy') { return "DataPact-Learning-$Role-20261024" }
    return "DataPact-$Instance-$Role"
}
function TaskArguments([string]$Role) {
    if ($Instance -eq 'legacy' -and $BackendPort -eq 8026 -and $FrontendPort -eq 3026) { return "`"$demoLauncher`" $Role" }
    return "`"$demoLauncher`" $Role --instance $Instance --backend-port $BackendPort --frontend-port $FrontendPort"
}
function AssertOwned([string]$Role) {
    $task = Get-ScheduledTask -TaskName (TaskName $Role) -ErrorAction SilentlyContinue
    if ($task -and ($task.Actions.Execute -ne $demoPython -or $task.Actions.Arguments -ne (TaskArguments $Role))) {
        throw "Task name belongs to a different launcher: $(TaskName $Role)"
    }
    return $task
}
foreach ($role in $demoRoles) { $null = AssertOwned $role }
if ($Action -eq 'Install') {
    & (Join-Path $demoRoot 'backend\.venv\Scripts\python.exe') $demoLauncher prepare --instance $Instance --backend-port $BackendPort --frontend-port $FrontendPort
    if ($LASTEXITCODE -ne 0) { throw 'Demo configuration preparation failed' }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    foreach ($role in $demoRoles) {
        if (-not (AssertOwned $role)) {
            $taskAction = New-ScheduledTaskAction -Execute $demoPython -Argument (TaskArguments $role) -WorkingDirectory $demoRoot
            Register-ScheduledTask -TaskName (TaskName $role) -Action $taskAction -Settings $settings -Principal $principal -Description 'Controlled local DataPact learning demo; loopback, mock payments, no paid models.' | Out-Null
        }
    }
}
if ($Action -eq 'Stop' -or $Action -in @('RestartBackend', 'RestartFrontend')) {
    $restartRole = if ($Action -eq 'RestartFrontend') { 'frontend' } else { 'backend' }
    $restartPort = if ($restartRole -eq 'frontend') { $FrontendPort } else { $BackendPort }
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
        $port = if ($role -eq 'backend') { $BackendPort } else { $FrontendPort }
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
