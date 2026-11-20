[CmdletBinding(SupportsShouldProcess)]
param([switch]$Remove)

$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$sid = $identity.User.Value
$name = "Gundam Station - $sid"
$description = "Start Gundam Station for $sid at interactive sign-in."
$service = New-Object -ComObject 'Schedule.Service'
$service.Connect()
$folder = $service.GetFolder('\')

if ($Remove) {
    $existing = $folder.GetTask($name)
    if ($existing.Definition.RegistrationInfo.Description -ne $description) {
        throw "A different task uses the name '$name'. It has been left in place."
    }
    if ($PSCmdlet.ShouldProcess($name, 'Remove sign-in task')) {
        $folder.DeleteTask($name, 0)
        Write-Output 'Gundam Station sign-in task removed.'
    }
    return
}

$station = Split-Path -Parent $PSScriptRoot
$exe = Get-Item -LiteralPath (Join-Path $station 'Launcher\Hangar.Launcher.exe')
$task = $service.NewTask(0)
$task.RegistrationInfo.Description = $description
$task.Principal.UserId = $sid
$task.Principal.LogonType = 3  # TASK_LOGON_INTERACTIVE_TOKEN
$task.Principal.RunLevel = 0   # Least privilege
$trigger = $task.Triggers.Create(9)  # TASK_TRIGGER_LOGON
$trigger.UserId = $sid
$action = $task.Actions.Create(0)    # TASK_ACTION_EXEC
$action.Path = $exe.FullName
$action.WorkingDirectory = $exe.DirectoryName
$task.Settings.DisallowStartIfOnBatteries = $false
$task.Settings.StopIfGoingOnBatteries = $false
$task.Settings.ExecutionTimeLimit = 'PT0S'
$task.Settings.MultipleInstances = 2  # Ignore a second start

if ($PSCmdlet.ShouldProcess($exe.FullName, "Create sign-in task '$name'")) {
    # TASK_CREATE fails if the name already exists. No stored credentials.
    $null = $folder.RegisterTaskDefinition($name, $task, 2, $sid, $null, 3, $null)
    Write-Output "Sign-in task created for $($identity.Name)."
}
