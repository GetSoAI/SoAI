[CmdletBinding(DefaultParameterSetName='Install')]
param(
    [Parameter(Mandatory=$true,ParameterSetName='Install')][string]$SetupPath,
    [Parameter(Mandatory=$true)][string]$InstallRoot,
    [Parameter(Mandatory=$true,ParameterSetName='Install')][string]$LockDir,
    [Parameter(Mandatory=$true)][string]$ReadyPath,
    [Parameter(Mandatory=$true,ParameterSetName='Install')][string]$TaskId,
    [Parameter(Mandatory=$true,ParameterSetName='Install')][string]$ToVersion,
    [Parameter(Mandatory=$true,ParameterSetName='Install')][int]$UpdaterPid,
    [Parameter(ParameterSetName='Install')][string]$StageRoot,
    [Parameter(Mandatory=$true,ParameterSetName='Recovery')]
    [Parameter(ParameterSetName='Install')][string]$TransactionPath,
    [Parameter(Mandatory=$true,ParameterSetName='Recovery')][int]$RecoveryLauncherPid,
    [Parameter(Mandatory=$true,ParameterSetName='Recovery')][long]$RecoveryLauncherStartTicks,
    [Parameter(ParameterSetName='Recovery')][string]$RelaunchArguments,
    [Parameter(ParameterSetName='Install')][switch]$RestartAfterUpdate
)

$ErrorActionPreference = 'Stop'
$handoffLockOwned = $false
$ownedUpdateProcessStopped = $true
$replacementStarted = $false
$activationCommitted = $false

function Write-UpdateDiagnostic {
    param(
        [Parameter(Mandatory=$true)][string]$Operation,
        [Parameter(Mandatory=$true)][Management.Automation.ErrorRecord]$Failure
    )
    try {
        $diagnostic = '[{0}] {1}{2}{3}{2}' -f [DateTime]::UtcNow.ToString('o'), $Operation, [Environment]::NewLine, ($Failure | Out-String)
        [IO.File]::AppendAllText((Join-Path $TransactionPath 'handoff-errors.log'), $diagnostic)
    }
    catch {
        Write-Warning "Failed to retain the diagnostic for Windows update operation '$Operation'."
    }
}

function Write-UpdateFailure {
    $recoveryPython = Join-Path $TransactionPath 'recovery_runtime\python.exe'
    $recoveryBackend = Join-Path $TransactionPath 'old\backend'
    $previousPythonPath = $env:PYTHONPATH
    $previousBytecodeSetting = $env:PYTHONDONTWRITEBYTECODE
    try {
        $env:PYTHONPATH = $recoveryBackend
        $env:PYTHONDONTWRITEBYTECODE = '1'
        $failureCode = @'
import sys
from app.updater.software_update.recovery_bootstrap import resolve_update_recovery_package_paths
sys.path.extend(resolve_update_recovery_package_paths(sys.argv[1]))
from app.updater.windows_update_transaction import publish_windows_update_failure
publish_windows_update_failure(*sys.argv[1:])
'@
        $failureArguments = '-P -S -c "{0}" "{1}" "{2}" "{3}"' -f $failureCode, $InstallRoot, $TransactionPath, $TaskId
        Invoke-OwnedUpdateProcess -Executable $recoveryPython -Arguments $failureArguments `
            -LogPath (Join-Path $TransactionPath 'failure-publication.log') -TimeoutMilliseconds 1800000
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
        $env:PYTHONDONTWRITEBYTECODE = $previousBytecodeSetting
    }
}

function Confirm-UpdateLockOwner {
    param([Parameter(Mandatory=$true)][int]$ExpectedPid)
    $verificationPython = Join-Path $TransactionPath 'recovery_runtime\python.exe'
    $verificationBackend = Join-Path $TransactionPath 'old\backend'
    if (!(Test-Path -LiteralPath $verificationPython -PathType Leaf) -or
        !(Test-Path -LiteralPath $verificationBackend -PathType Container)) {
        throw 'Retained update ownership verification is missing; preserve the transaction for repair.'
    }
    $previousPythonPath = $env:PYTHONPATH
    $previousBytecodeSetting = $env:PYTHONDONTWRITEBYTECODE
    try {
        $env:PYTHONPATH = $verificationBackend
        $env:PYTHONDONTWRITEBYTECODE = '1'
        $verificationCode = @'
import sys
from app.updater.software_update.recovery_bootstrap import resolve_update_recovery_package_paths
sys.path.extend(resolve_update_recovery_package_paths(sys.argv[1]))
from app.updater.software_update.update_lock import require_software_update_lock_owner
require_software_update_lock_owner(sys.argv[2], base_path=sys.argv[1], edition='soai-core', expected_pid=int(sys.argv[3]))
'@
        $verificationArguments = '-P -S -c "{0}" "{1}" "{2}" {3}' -f $verificationCode, $InstallRoot, $LockDir, $ExpectedPid
        Invoke-OwnedUpdateProcess -Executable $verificationPython -Arguments $verificationArguments `
            -LogPath (Join-Path $TransactionPath 'lock-verification.log') -TimeoutMilliseconds 1800000
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
        $env:PYTHONDONTWRITEBYTECODE = $previousBytecodeSetting
    }
}

function Release-UpdateLock {
    if (!$handoffLockOwned) {
        return
    }
    if (!(Test-Path -LiteralPath $LockDir -PathType Container)) {
        throw 'The SoAI installer handoff lock disappeared before release.'
    }
    $pidPath = Join-Path $LockDir 'pid'
    if (!(Test-Path -LiteralPath $pidPath -PathType Leaf)) {
        throw 'The SoAI installer handoff lock lost its owner record.'
    }
    Confirm-UpdateLockOwner -ExpectedPid $PID
    Remove-Item -LiteralPath (Join-Path $LockDir 'process.json') -Force
    Remove-Item -LiteralPath $pidPath -Force
    Remove-Item -LiteralPath $LockDir -Force
    $script:handoffLockOwned = $false
}

function Start-SoAILauncher {
    param([string]$Arguments = '')
    $launcherPath = Join-Path $InstallRoot 'soai.exe'
    if (!(Test-Path -LiteralPath $launcherPath -PathType Leaf)) {
        throw 'The installed launcher is missing; startup was not attempted.'
    }
    $startInfo = New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName = $launcherPath
    $startInfo.Arguments = $Arguments
    $startInfo.WorkingDirectory = $InstallRoot
    $startInfo.UseShellExecute = $false
    $launcher = [Diagnostics.Process]::Start($startInfo)
    if (!$launcher) { throw 'The installed launcher process could not be created.' }
    $launcher.Dispose()
}

function Remove-OwnedTemporaryFile {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Description
    )
    if (!(Test-Path -LiteralPath $Path)) {
        return
    }
    try {
        Remove-Item -LiteralPath $Path -Force
    }
    catch {
        Write-Warning "Failed to remove the temporary $Description."
    }
}

function Invoke-OwnedUpdateProcess {
    param(
        [Parameter(Mandatory=$true)][string]$Executable,
        [Parameter(Mandatory=$true)][string]$Arguments,
        [Parameter(Mandatory=$true)][string]$LogPath,
        [Parameter(Mandatory=$true)][int]$TimeoutMilliseconds,
        [bool]$RetainReadyBackend = $false
    )
    $script:ownedUpdateProcessStopped = $false
    $ownershipTransferred = $false
    $operation = [SoAILauncher.NativeBackendJob]::StartProcess(
        $Executable, $Arguments, $InstallRoot, $LogPath
    )
    try {
        if (!$operation.ProcessHandle.WaitForExit($TimeoutMilliseconds)) {
            throw 'The Windows update operation exceeded its deadline.'
        }
        if ($operation.ProcessHandle.ExitCode -ne 0) {
            throw "The Windows update operation exited with code $($operation.ProcessHandle.ExitCode)."
        }
        if ($RetainReadyBackend) {
            $operation.Commit()
            $ownershipTransferred = $true
        }
    }
    finally {
        $operation.Dispose()
        $script:ownedUpdateProcessStopped = !$ownershipTransferred
    }
}

function Invoke-UpdateActivation {
    $recoveryPython = Join-Path $TransactionPath 'recovery_runtime\python.exe'
    $recoveryBackend = Join-Path $TransactionPath 'old\backend'
    $previousPythonPath = $env:PYTHONPATH
    $previousBytecodeSetting = $env:PYTHONDONTWRITEBYTECODE
    try {
        $env:PYTHONPATH = $recoveryBackend
        $env:PYTHONDONTWRITEBYTECODE = '1'
        $activationCode = @'
import sys
from app.updater.software_update.recovery_bootstrap import resolve_update_recovery_package_paths
sys.path.extend(resolve_update_recovery_package_paths(sys.argv[1]))
from app.updater.windows_update_transaction import activate_windows_update_transaction
raise SystemExit(0 if activate_windows_update_transaction(*sys.argv[1:]) else 1)
'@
        $activationArguments = '-P -S -c "{0}" "{1}" "{2}" "{3}"' -f $activationCode, $InstallRoot, $TransactionPath, $TaskId
        Invoke-OwnedUpdateProcess -Executable $recoveryPython -Arguments $activationArguments `
            -LogPath (Join-Path $TransactionPath 'activation.log') -TimeoutMilliseconds 1800000 `
            -RetainReadyBackend $true
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
        $env:PYTHONDONTWRITEBYTECODE = $previousBytecodeSetting
    }
}

function Restore-FailedUpdateTransaction {
    if (!$ownedUpdateProcessStopped) {
        throw 'Windows update recovery requires verified exit of the installer process tree.'
    }
    $recoveryPython = Join-Path $TransactionPath 'recovery_runtime\python.exe'
    $recoveryBackend = Join-Path $TransactionPath 'old\backend'
    if (!(Test-Path -LiteralPath $recoveryPython -PathType Leaf) -or
        !(Test-Path -LiteralPath $recoveryBackend -PathType Container)) {
        throw 'Windows update recovery dependencies are missing; preserve the transaction for repair.'
    }
    Release-UpdateLock
    $previousPythonPath = $env:PYTHONPATH
    $previousBytecodeSetting = $env:PYTHONDONTWRITEBYTECODE
    try {
        $env:PYTHONPATH = $recoveryBackend
        $env:PYTHONDONTWRITEBYTECODE = '1'
        $recoveryCode = @'
import os, sys
from app.updater.software_update.recovery_bootstrap import resolve_update_recovery_package_paths
sys.path.extend(resolve_update_recovery_package_paths(sys.argv[1]))
from app.updater.software_update.install_transaction_recovery import restore_transaction
from app.updater.software_update.install_transaction_state import ROLLBACK_COMPLETE_MARKER, marker_path, paths_from_transaction_directory, build_rollback_top_level_ignore_patterns
from core.logging.trace import get_logger
restored = restore_transaction(paths=paths_from_transaction_directory(sys.argv[1], sys.argv[2]), top_level_ignore_patterns=build_rollback_top_level_ignore_patterns(sys.argv[2]), logger=get_logger('SoAI.app.updater.windows_update_transaction'), cleanup_after_recovery=False)
raise SystemExit(0 if restored and os.path.isfile(marker_path(sys.argv[2], ROLLBACK_COMPLETE_MARKER)) else 1)
'@
        $recoveryArguments = '-P -S -c "{0}" "{1}" "{2}"' -f $recoveryCode, $InstallRoot, $TransactionPath
        Invoke-OwnedUpdateProcess -Executable $recoveryPython -Arguments $recoveryArguments `
            -LogPath (Join-Path $TransactionPath 'restoration.log') -TimeoutMilliseconds 1800000
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
        $env:PYTHONDONTWRITEBYTECODE = $previousBytecodeSetting
    }
}

function Invoke-LauncherRecovery {
    $launcher = $null
    $recovery = $null
    $previousPythonPath = $env:PYTHONPATH
    $previousBytecode = $env:PYTHONDONTWRITEBYTECODE
    $previousConfigPath = $env:SOAI_CONFIG_PATH
    try {
        $launcher = [Diagnostics.Process]::GetProcessById($RecoveryLauncherPid)
        $launcherHandle = $launcher.Handle
        if ($launcherHandle -eq [IntPtr]::Zero -or $launcher.HasExited -or
            $launcher.StartTime.ToUniversalTime().Ticks -ne $RecoveryLauncherStartTicks -or
            ![string]::Equals($launcher.MainModule.FileName, (Join-Path $InstallRoot 'soai.exe'), [StringComparison]::OrdinalIgnoreCase)) {
            throw 'The recovery launcher identity could not be verified; no restoration was attempted.'
        }
        $recoveryPython = Join-Path $TransactionPath 'recovery_runtime\python.exe'
        $recoveryBackend = Join-Path $TransactionPath 'old\backend'
        if (!(Test-Path -LiteralPath $recoveryPython -PathType Leaf) -or
            !(Test-Path -LiteralPath $recoveryBackend -PathType Container)) {
            throw 'Retained recovery implementation is missing; preserve the transaction for repair.'
        }
        $env:PYTHONPATH = $recoveryBackend
        $env:PYTHONDONTWRITEBYTECODE = '1'
        $recoveryCode = @'
import json, sys
from app.updater.software_update.recovery_bootstrap import resolve_update_recovery_package_paths
sys.path.extend(resolve_update_recovery_package_paths(sys.argv[1]))
from app.updater.windows_update_recovery import recover_after_launcher_exit
from core.logging.trace import get_logger
config_path = recover_after_launcher_exit(base_path=sys.argv[1], transaction_path=sys.argv[2], launcher_pid=int(sys.argv[3]), supervisor_pid=int(sys.argv[4]), ready_path=sys.argv[5], logger=get_logger('SoAI.app.updater.windows_recovery'))
print(json.dumps(config_path))
'@
        $recovery = Start-Process -FilePath $recoveryPython -ArgumentList ('-P -S -c "{0}" "{1}" "{2}" {3} {4} "{5}"' -f $recoveryCode, $InstallRoot, $TransactionPath, $RecoveryLauncherPid, $PID, $ReadyPath) `
            -WorkingDirectory $InstallRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $TransactionPath 'launcher-recovery.stdout.log') `
            -RedirectStandardError (Join-Path $TransactionPath 'launcher-recovery.stderr.log')
        $recoveryHandle = $recovery.Handle
        if ($recoveryHandle -eq [IntPtr]::Zero -or !$recovery.WaitForExit(1800000)) {
            throw 'The shared recovery process did not finish within its deadline.'
        }
        if ($recovery.ExitCode -ne 0) {
            throw 'Shared update recovery failed; preserve the transaction for repair.'
        }
        $recovery.Dispose(); $recovery = $null
        $env:PYTHONPATH = $previousPythonPath
        $env:PYTHONDONTWRITEBYTECODE = $previousBytecode
        $restoredConfigPath = Get-Content -LiteralPath (Join-Path $TransactionPath 'launcher-recovery.stdout.log') -Raw | ConvertFrom-Json
        if ($restoredConfigPath -isnot [string] -or [string]::IsNullOrWhiteSpace($restoredConfigPath)) {
            throw 'Shared recovery did not return the restored configuration selection.'
        }
        $env:SOAI_CONFIG_PATH = $restoredConfigPath
        Start-SoAILauncher -Arguments $RelaunchArguments
    }
    finally {
        if ($launcher) { $launcher.Dispose() }
        if ($recovery) {
            try {
                if (!$recovery.HasExited) {
                    $recovery.Kill()
                    if (!$recovery.WaitForExit(30000)) { throw 'The recovery process remains active; retained files must not be cleaned.' }
                }
            }
            finally { $recovery.Dispose() }
        }
        $env:PYTHONPATH = $previousPythonPath
        $env:PYTHONDONTWRITEBYTECODE = $previousBytecode
        $env:SOAI_CONFIG_PATH = $previousConfigPath
    }
}

if ($PSCmdlet.ParameterSetName -eq 'Recovery') {
    Invoke-LauncherRecovery
    exit 0
}

if (![string]::IsNullOrWhiteSpace($StageRoot)) {
    $preparation = $null
    $preparationStopped = $false
    $preparationDisposalAttempted = $false
    try {
        $setupMetadata = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($SetupPath)
        if ($setupMetadata.Comments -cne 'SoAI installer supports /PrepareUpdate extraction without installation.' -or
            $setupMetadata.ProductName -cne 'SoAI' -or $setupMetadata.ProductVersion -cne $ToVersion) {
            throw 'The signed Windows installer does not support safe preparation for the expected product version.'
        }
        Add-Type -Path (Join-Path $TransactionPath 'native_job\soai-job-owner.dll')
        $preparation = [SoAILauncher.NativeBackendJob]::StartProcess(
            $SetupPath,
            ('/S /PrepareUpdate="{0}"' -f $StageRoot),
            $InstallRoot,
            "$StageRoot.preparation.log"
        )
        if (!$preparation.ProcessHandle.WaitForExit(600000)) {
            throw 'The Windows installer preparation exceeded its deadline.'
        }
        $preparationExitCode = $preparation.ProcessHandle.ExitCode
        $preparationDisposalAttempted = $true
        $preparation.Dispose()
        $preparationStopped = $true
        if ($preparationExitCode -ne 0) {
            exit $preparationExitCode
        }
        $inventoryScript = Join-Path $StageRoot 'installer-support\Preserve-SoAIUpgrade.ps1'
        $nativeInventory = & $inventoryScript -InstallRoot $InstallRoot -Mode Inventory
        if ($LASTEXITCODE -ne 0) {
            throw 'The Windows installer could not describe its rollback inventory.'
        }
        Set-Content -LiteralPath "$StageRoot.inventory.json" -Value $nativeInventory -Encoding ASCII
        exit 0
    }
    finally {
        if ($null -ne $preparation -and !$preparationDisposalAttempted) {
            $preparationDisposalAttempted = $true
            $preparation.Dispose()
            $preparationStopped = $true
        }
        if ($preparationStopped) {
            Set-Content -LiteralPath "$StageRoot.exited" -Value ([string]$PID) -Encoding ASCII
        }
    }
}

try {
    if ([string]::IsNullOrWhiteSpace($TransactionPath)) {
        throw 'The Windows update has no retained transaction.'
    }
    Add-Type -Path (Join-Path $TransactionPath 'native_job\soai-job-owner.dll')
    $updaterProcess = Get-Process -Id $UpdaterPid -ErrorAction Stop
    Confirm-UpdateLockOwner -ExpectedPid $UpdaterPid
    Set-Content -LiteralPath $ReadyPath -Value ([string]$PID) -Encoding ASCII
    if (!$updaterProcess.WaitForExit(120000)) {
        throw 'The SoAI updater process did not exit before the installer handoff deadline.'
    }
    Confirm-UpdateLockOwner -ExpectedPid $PID
    $handoffLockOwned = $true

    $previousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $TransactionPath 'old\backend'
        $beginCode = @'
import sys
from app.updater.software_update.recovery_bootstrap import resolve_update_recovery_package_paths
sys.path.extend(resolve_update_recovery_package_paths(sys.argv[1]))
from app.updater.windows_update_admission import begin_windows_update_transaction
begin_windows_update_transaction(*sys.argv[1:])
'@
        $beginArguments = '-B -P -S -c "{0}" "{1}" "{2}" "{3}"' -f $beginCode, $InstallRoot, $TransactionPath, $TaskId
        Invoke-OwnedUpdateProcess -Executable (Join-Path $TransactionPath 'recovery_runtime\python.exe') `
            -Arguments $beginArguments -LogPath (Join-Path $TransactionPath 'replacement-admission.log') `
            -TimeoutMilliseconds 1800000
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
    }
    $replacementStarted = $true
    Invoke-OwnedUpdateProcess -Executable $SetupPath -Arguments ("/S /D=$InstallRoot") `
        -LogPath (Join-Path $TransactionPath 'installer.log') -TimeoutMilliseconds 1800000
    $launcherPath = Join-Path $InstallRoot 'soai.exe'
    $markerPath = Join-Path $InstallRoot '.soai-install-root'
    if (!(Test-Path -LiteralPath $launcherPath -PathType Leaf) -or
        !(Test-Path -LiteralPath $markerPath -PathType Leaf) -or
        !(Get-Content -LiteralPath $markerPath | Where-Object { $_ -eq "Version=$ToVersion" })) {
        throw 'The SoAI installer did not produce the expected installed version.'
    }
    $previousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = (Join-Path $InstallRoot 'backend') + ';' + $InstallRoot
        $finishArguments = '-P -c "import sys; from app.updater.windows_update_transaction import finish_windows_update_transaction; finish_windows_update_transaction(*sys.argv[1:])" "{0}" "{1}" "{2}"' -f $InstallRoot, $TransactionPath, $TaskId
        Invoke-OwnedUpdateProcess -Executable (Join-Path $InstallRoot 'soai_main_venv\Scripts\python.exe') `
            -Arguments $finishArguments -LogPath (Join-Path $TransactionPath 'target-preparation.log') `
            -TimeoutMilliseconds 1800000
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
    }
    Release-UpdateLock
    if ($RestartAfterUpdate) {
        Invoke-UpdateActivation
        $activationCommitted = $true
        Start-SoAILauncher
    }
    exit 0
}
catch {
    Write-UpdateDiagnostic -Operation 'installer-handoff' -Failure $_
    $restored = $false
    if ($replacementStarted -and !$activationCommitted -and $ownedUpdateProcessStopped) {
        try {
            Restore-FailedUpdateTransaction
            $restored = $true
        }
        catch {
            Write-UpdateDiagnostic -Operation 'automatic-restoration' -Failure $_
            Write-Warning 'Automatic Windows update restoration failed; retained transaction evidence requires repair.'
        }
    }
    if (!$activationCommitted -and $ownedUpdateProcessStopped) {
        try {
            Write-UpdateFailure
        }
        catch {
            Write-UpdateDiagnostic -Operation 'failure-publication' -Failure $_
            Write-Warning 'Failed to persist the Windows installer update result.'
        }
    }
    if ($restored) {
        Write-Warning 'The previous application files, runtime, and state were restored; retained recovery material awaits cleanup.'
        if ($RestartAfterUpdate) {
            try {
                Start-SoAILauncher
            }
            catch {
                Write-UpdateDiagnostic -Operation 'restored-launcher-start' -Failure $_
                Write-Warning 'The previous installation was restored, but its desktop launcher could not start.'
            }
        }
    }
    elseif ($activationCommitted) {
        Write-Warning 'The update completed activation, but its desktop launcher could not start.'
    }
    else {
        Write-Warning 'Windows update recovery is required before the installation can start; retained transaction evidence must be preserved.'
    }
    exit 1
}
finally {
    Remove-OwnedTemporaryFile -Path $SetupPath -Description 'SoAI setup executable'
    Remove-OwnedTemporaryFile -Path $ReadyPath -Description 'installer handoff readiness file'
    Remove-OwnedTemporaryFile -Path $PSCommandPath -Description 'installer handoff script'
    Release-UpdateLock
}
