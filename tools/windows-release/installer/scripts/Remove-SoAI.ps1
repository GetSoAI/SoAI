# SoAI Windows installation cleanup and completion verification [Remove-SoAI.ps1]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InstallRoot,
    [ValidateSet('Uninstall','ArchiveUninstall','Upgrade','Stop','VerifyUninstall')][string]$Mode = 'Uninstall',
    [string]$ManifestPath = '',
    [string]$ControlLauncherPath = '',
    [string]$VerificationPath = '',
    [switch]$RemoveApplicationData,
    [switch]$InstallerRollback
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Shared-SoAIResourceOwnership.ps1')
trap { if ($env:SOAI_INSTALLER_FAILURE_PATH) { try { [IO.File]::WriteAllText($env:SOAI_INSTALLER_FAILURE_PATH, (($_.Exception.Message -replace '\s+', ' ').Trim()), [Text.Encoding]::Unicode) } catch { } }; break }
[AppContext]::SetSwitch('Switch.System.IO.UseLegacyPathHandling', $false)
[AppContext]::SetSwitch('Switch.System.IO.BlockLongPaths', $false)

function ConvertTo-RemovalFilesystemPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    if ($Path.StartsWith('\\?\', [StringComparison]::Ordinal)) { return $Path }
    if ($Path.StartsWith('\\', [StringComparison]::Ordinal)) { return '\\?\UNC\' + $Path.Substring(2) }
    return '\\?\' + [IO.Path]::GetFullPath($Path)
}

function Initialize-RemovalAdmission {
    param([Parameter(Mandatory=$true)][string]$Root)
    $lockDirectory = $Root.TrimEnd('\') + '\data\state\locks\soai.install.lock.d'
    if ($env:SOAI_INSTALL_LOCK_HELD_PATH) {
        $script:removalGate = [Threading.Mutex]::OpenExisting('Global\SoAI.WindowsInstaller.V1')
    }
    else {
        $created = $false
        $script:removalGate = New-Object Threading.Mutex($false, 'Global\SoAI.WindowsInstaller.V1', [ref]$created)
        if (!$created) { throw 'Another SoAI installer or repair operation is active. No application files were removed.' }
    }
    $launcher = Join-Path $Root 'soai.exe'
    if (![string]::IsNullOrWhiteSpace($ControlLauncherPath) -or [IO.File]::Exists((ConvertTo-RemovalFilesystemPath $launcher))) {
        $controlLauncher = if ([string]::IsNullOrWhiteSpace($ControlLauncherPath)) { $launcher } else { [IO.Path]::GetFullPath($ControlLauncherPath) }
        [Reflection.Assembly]::Load([IO.File]::ReadAllBytes((ConvertTo-RemovalFilesystemPath $controlLauncher))) | Out-Null
    }
    else {
        throw 'The SoAI control launcher is missing. Run the current SoAI installer to repair this installation before removing it. No application files were removed.'
    }
    if ($env:SOAI_INSTALL_LOCK_HELD_PATH) { Assert-RemovalAdmissionOwner -LockDirectory $lockDirectory }
    [SoAILauncher.NativeBackendJob]::PrepareTemporaryEnvironment()
    if ($env:SOAI_INSTALL_LOCK_HELD_PATH) { return }
    $current = [IO.Path]::GetFullPath($Root)
    $ancestors = New-Object System.Collections.Generic.List[string]
    while ($true) {
        $ancestors.Add($current)
        $parent = [IO.Path]::GetDirectoryName($current.TrimEnd('\'))
        if (!$parent) { break }
        $current = $parent
    }
    for ($index = $ancestors.Count - 1; $index -ge 0; $index -= 1) {
        Retain-RemovalDirectory -Path $ancestors[$index]
    }
    foreach ($relative in @('data', 'data\locks', 'data\state', 'data\state\locks')) {
        $directory = $Root.TrimEnd('\') + '\' + $relative
        $nativeDirectory = ConvertTo-RemovalFilesystemPath $directory
        if (![IO.Directory]::Exists($nativeDirectory)) {
            if (![SoAILauncher.NativeFilesystemHandles]::CreateDirectory($nativeDirectory, [IntPtr]::Zero)) {
                throw 'The removal admission directory could not be created exclusively.'
            }
        }
        Retain-RemovalDirectory -Path $directory
    }
    Remove-CommittedUpdateStorage -Root $Root
    $transactionPath = ConvertTo-RemovalFilesystemPath ($Root.TrimEnd('\') + '\data\locks\soai.installation.transaction.lock')
    $script:removalTransaction = [IO.File]::Open($transactionPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::ReadWrite)
    $script:removalTransaction.Lock(0, 1)
    $null = Assert-SafeInstallRoot -Root $Root
    foreach ($entry in [IO.Directory]::GetFileSystemEntries((ConvertTo-RemovalFilesystemPath $Root))) {
        $name = [IO.Path]::GetFileName($entry)
        if (!$RemoveApplicationData -and (Test-RetainedUpdateStorageName -EntryName $name)) { throw 'An update awaits recovery; removal has not changed application files.' }
    }
    foreach ($name in @('backup_restore_journal.json')) {
        if ([IO.File]::Exists((ConvertTo-RemovalFilesystemPath ($Root.TrimEnd('\') + '\data\state\' + $name)))) {
            throw 'Backup restoration awaits recovery; removal has not changed application files.'
        }
    }
    $nativeLock = ConvertTo-RemovalFilesystemPath $lockDirectory
    $retainedLock = [SoAILauncher.NativeFilesystemHandles]::RecoverAbandonedInstallLock($lockDirectory)
    if ($retainedLock) { Write-Host ('Recovered abandoned installation ownership. Evidence: ' + $retainedLock) }
    if (![SoAILauncher.NativeFilesystemHandles]::CreateDirectory($nativeLock, [IntPtr]::Zero)) {
        throw 'An existing install lock requires verified recovery. Its ownership evidence was retained.'
    }
    $script:removalOwnedLock = $lockDirectory
    Retain-RemovalDirectory -Path $lockDirectory
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $bytes = New-Object byte[] 32
        $random.GetBytes($bytes)
        $script:removalToken = [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
    } finally { $random.Dispose() }
    [IO.File]::WriteAllText($nativeLock + '\pid', $PID.ToString([Globalization.CultureInfo]::InvariantCulture), [Text.Encoding]::ASCII)
    [IO.File]::WriteAllText($nativeLock + '\token', $script:removalToken, [Text.Encoding]::ASCII)
    $process = Get-Process -Id $PID -ErrorAction Stop
    try {
        $seconds = [double]$process.StartTime.ToUniversalTime().ToFileTimeUtc() / 10000000.0 - 11644473600.0
        $started = [long][Math]::Floor($seconds * 1000.0)
    } finally { $process.Dispose() }
    [IO.File]::WriteAllText($nativeLock + '\owner-start-ms', $started.ToString([Globalization.CultureInfo]::InvariantCulture), [Text.Encoding]::ASCII)
    $env:SOAI_INSTALL_LOCK_HELD_PATH = $lockDirectory
    $env:SOAI_INSTALL_LOCK_HELD_TOKEN = $script:removalToken
    $env:SOAI_INSTALL_LOCK_OWNER_START_MS = $started.ToString([Globalization.CultureInfo]::InvariantCulture)
}

function Retain-RemovalDirectory {
    param([Parameter(Mandatory=$true)][string]$Path)
    $nativePath = ConvertTo-RemovalFilesystemPath $Path
    $handle = [SoAILauncher.NativeFilesystemHandles]::CreateFile($nativePath, 0x80, 3, [IntPtr]::Zero, 3, 0x02200000, [IntPtr]::Zero)
    if ($handle.IsInvalid) { $handle.Dispose(); throw 'The removal ancestor could not be retained.' }
    $script:removalHandles.Add($handle)
    $attributes = [SoAILauncher.NativeFilesystemHandles]::GetFileAttributes($nativePath)
    if ($attributes -eq [uint32]::MaxValue -or ($attributes -band 0x400) -ne 0 -or ($attributes -band 0x10) -eq 0) {
        throw 'A removal ancestor is not a safe retained directory.'
    }
}

function Assert-RemovalAdmissionOwner {
    param([Parameter(Mandatory=$true)][string]$LockDirectory)
    if (![string]::Equals([IO.Path]::GetFullPath($env:SOAI_INSTALL_LOCK_HELD_PATH).TrimEnd('\'), $LockDirectory.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The removal admission target does not match.'
    }
    $nativeLock = ConvertTo-RemovalFilesystemPath $LockDirectory
    $token = [IO.File]::ReadAllText($nativeLock + '\token').Trim()
    if ($token -cnotmatch '^[0-9a-f]{64}$' -or $token -cne $env:SOAI_INSTALL_LOCK_HELD_TOKEN) { throw 'The removal admission token does not match.' }
    $ownerPid = [int][IO.File]::ReadAllText($nativeLock + '\pid').Trim()
    $owner = Get-Process -Id $ownerPid -ErrorAction Stop
    try {
        $seconds = [double]$owner.StartTime.ToUniversalTime().ToFileTimeUtc() / 10000000.0 - 11644473600.0
        $started = [long][Math]::Floor($seconds * 1000.0)
        if ($owner.HasExited -or $started.ToString([Globalization.CultureInfo]::InvariantCulture) -cne $env:SOAI_INSTALL_LOCK_OWNER_START_MS) {
            throw 'The removal admission process identity does not match.'
        }
        if ($ownerPid -eq $PID) { return }
        $processId = $PID
        $childCreated = $null
        for ($depth = 0; $depth -lt 128; $depth += 1) {
            $process = Get-Process -Id $processId -ErrorAction Stop
            try {
                $created = $process.StartTime.ToUniversalTime()
                if ($null -ne $childCreated -and $created -gt $childCreated) { throw 'The removal admission ancestry changed process identity.' }
                $parentId = [SoAILauncher.NativeFilesystemHandles]::GetParentProcessId($process)
                $childCreated = $created
            } finally { $process.Dispose() }
            if ($parentId -eq 0) { break }
            if ($parentId -eq $ownerPid -and $owner.StartTime.ToUniversalTime() -le $childCreated) { return }
            $processId = $parentId
        }
        throw 'The removal process is not a child of its verified admission owner.'
    } finally { $owner.Dispose() }
}

function Write-Step {
    param([Parameter(Mandatory=$true)][string]$Message)
    Write-Host "[SoAI] $Message"
}

function Resolve-FullPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $executionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
}

function Resolve-ChildPath {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$Child
    )
    $rootFull = Resolve-FullPath $Root
    $combined = Resolve-FullPath (Join-Path $rootFull $Child)
    $prefix = $rootFull.TrimEnd('\') + '\'
    if (!$combined.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to touch a path outside the SoAI installation root: $combined"
    }
    return $combined
}

function Test-RetainedUpdateStorageName {
    param([Parameter(Mandatory=$true)][string]$EntryName, [switch]$CleanupOnly)
    $cleanup = $EntryName.StartsWith('.soai_update_cleanup_', [StringComparison]::OrdinalIgnoreCase)
    if ($CleanupOnly) { return $cleanup }
    return $EntryName.StartsWith('.soai_update_transaction_', [StringComparison]::OrdinalIgnoreCase) -or $cleanup
}

function Remove-CommittedUpdateStorage {
    param([Parameter(Mandatory=$true)][string]$Root)
    $nativeRoot = ConvertTo-RemovalFilesystemPath $Root
    if (![IO.Directory]::Exists($nativeRoot)) { return }
    $retained = @([IO.Directory]::GetFileSystemEntries($nativeRoot) | Where-Object { Test-RetainedUpdateStorageName -EntryName ([IO.Path]::GetFileName($_)) })
    if ($retained.Count -eq 0) { return }
    $removal = if ($Mode -in @('Uninstall', 'ArchiveUninstall')) { 'uninstall' } else { 'recover' }
    if ($removal -eq 'recover') {
        foreach ($entry in $retained) {
            if (!((Test-RetainedUpdateStorageName -EntryName ([IO.Path]::GetFileName($entry)) -CleanupOnly) -or [IO.File]::Exists($entry + '\success_complete'))) { return }
        }
    }
    $python = Join-Path $Root 'soai_main_venv\Scripts\python.exe'
    if (!(Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $python) -PathType Leaf)) { return }
    $source = @'
import logging
import sys
from app.updater.software_update.committed_transaction_disposal import discard_unstarted_installer_activation, dispose_committed_update_storage_once
from app.updater.software_update.install_transaction_recovery import recover_interrupted_update_transactions
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('installer.update_cleanup')
if sys.argv[2] == 'uninstall':
    discard_unstarted_installer_activation(sys.argv[1])
    sys.exit(0 if dispose_committed_update_storage_once(sys.argv[1], logger) else 1)
sys.exit(0 if recover_interrupted_update_transactions(sys.argv[1], logger) else 1)
'@
    $priorPythonPath = $env:PYTHONPATH
    $priorBytecode = $env:PYTHONDONTWRITEBYTECODE
    try {
        $env:PYTHONPATH = $Root.TrimEnd('\') + '\backend'
        $env:PYTHONDONTWRITEBYTECODE = '1'
        & $python -B -P -c $source $Root $removal | Out-Host
    }
    finally {
        $env:PYTHONPATH = $priorPythonPath
        $env:PYTHONDONTWRITEBYTECODE = $priorBytecode
    }
}

function Assert-SafeInstallRoot {
    param([Parameter(Mandatory=$true)][string]$Root, [switch]$DeferRetainedUpdateCheck)
    $full = Resolve-FullPath $Root
    $driveRoot = [System.IO.Path]::GetPathRoot($full).TrimEnd('\')
    $trimmed = $full.TrimEnd('\')
    $blocked = @(
        $driveRoot,
        $env:WINDIR,
        $env:ProgramFiles,
        ${env:ProgramFiles(x86)},
        $env:USERPROFILE
    ) | Where-Object { $_ }

    foreach ($path in $blocked) {
        if ([string]::Equals($trimmed, $path.TrimEnd('\'), [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clean unsafe installation root: $full"
        }
    }
    foreach ($filename in @('.soai_install_manifest.json', 'release-info-v1.json')) {
        $identityPath = ConvertTo-RemovalFilesystemPath ($full.TrimEnd('\') + '\' + $filename)
        if ([IO.File]::Exists($identityPath)) {
            $identity = [IO.File]::ReadAllText($identityPath) | ConvertFrom-Json
            if ($identity.schema_version -ne 1 -or $identity.product -cne 'SoAI' -or $identity.edition -cne 'soai-core') {
                throw 'The removal target identity is invalid or belongs to another edition. No application files were removed.'
            }
        }
    }

    $marker = Join-Path $full '.soai-install-root'
    $looksLikeSoAI = (Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath (Join-Path $full 'soai.exe'))) -and
        (Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath (Join-Path $full 'backend'))) -and
        (Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath (Join-Path $full 'frontend')))
    if ($Mode -in @('Uninstall', 'ArchiveUninstall') -and !(Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $marker))) {
        $rootChildren = @()
        if (Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $full) -PathType Container) {
            $rootChildren = @(Get-ChildItem -LiteralPath (ConvertTo-RemovalFilesystemPath $full) -Force -ErrorAction Stop)
        }
        $isEmptyInstallRoot = $rootChildren.Count -eq 0
        $isOnlyStaleUninstaller = $rootChildren.Count -eq 1 -and
            [string]::Equals($rootChildren[0].Name, 'Uninstall.exe', [System.StringComparison]::OrdinalIgnoreCase) -and
            [string]::Equals((Split-Path -Leaf $full), 'SoAI', [System.StringComparison]::OrdinalIgnoreCase)
        if (!$isEmptyInstallRoot -and !$looksLikeSoAI -and !$isOnlyStaleUninstaller) {
            throw "SoAI install marker is missing. Refusing to uninstall from $full."
        }
    }
    if ($Mode -in @('Upgrade', 'Stop') -and !(Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $marker)) -and !$looksLikeSoAI) {
        throw "The target does not look like a SoAI installation: $full"
    }
    if (!$DeferRetainedUpdateCheck -and $Mode -in @('Uninstall', 'ArchiveUninstall') -and (Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $full) -PathType Container)) {
        foreach ($entry in Get-ChildItem -LiteralPath (ConvertTo-RemovalFilesystemPath $full) -Force -ErrorAction Stop) {
            if (Test-RetainedUpdateStorageName -EntryName $entry.Name) {
                throw 'A software update awaits recovery or cleanup. Reopen SoAI to complete it before uninstalling. No application files were removed.'
            }
        }
    }
    return $full
}

function Resolve-InstalledControlPython {
    param([Parameter(Mandatory=$true)][string]$Root, [switch]$All)
    foreach ($relative in @('soai_main_venv\Scripts\python.exe', 'python\python.exe', 'python-3.13\python.exe', 'runtime\python\python.exe', 'runtime\python-3.13\python.exe', 'soai_python\python.exe')) {
        $candidate = Join-Path $Root $relative
        if (!(Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $candidate) -PathType Leaf)) { continue }
        if (!$All) { return $candidate }
        $candidate
        $windowed = Join-Path ([IO.Path]::GetDirectoryName($candidate)) 'pythonw.exe'
        if (Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $windowed) -PathType Leaf) { $windowed }
    }
    if (!$All) { throw 'The installed control runtime is missing; no application files were changed.' }
}

function Invoke-RemovalControlCommand {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$Executable,
        [Parameter(Mandatory=$true)][string]$Arguments,
        [Parameter(Mandatory=$true)][ValidateSet('stop','shutdown-verification')][string]$Phase
    )
    $logBase = $script:removalDiagnosticRoot + '\' + $Phase + '-' + [Guid]::NewGuid().ToString('N')
    $recordPath = ConvertTo-RemovalFilesystemPath ($logBase + '.command.json')
    $stdoutPath = ConvertTo-RemovalFilesystemPath ($logBase + '.out.log')
    $stderrPath = ConvertTo-RemovalFilesystemPath ($logBase + '.err.log')
    $record = [ordered]@{ phase=$Phase; install_root=$Root; executable=$Executable; arguments=$Arguments; stdout=$stdoutPath; stderr=$stderrPath; outcome='running'; exit_code=$null; failure=$null }
    [IO.File]::WriteAllText($recordPath, ($record | ConvertTo-Json), [Text.Encoding]::UTF8)
    $startInfo = New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName = $Executable
    $startInfo.Arguments = $Arguments
    $startInfo.WorkingDirectory = $Root
    $startInfo.UseShellExecute = $false
    $job = $null
    try {
        $job = [SoAILauncher.NativeBackendJob]::StartLoggedProcess($startInfo, $stdoutPath, $stderrPath)
        if (!$job.ProcessHandle.WaitForExit(60000)) {
            $record.outcome = 'timed_out'
            throw "SoAI $Phase timed out. Diagnostics: $script:removalDiagnosticRoot"
        }
        $record.exit_code = $job.ExitCode
        $record.outcome = if ($job.ExitCode -eq 0) { 'succeeded' } else { 'failed' }
        return $job.ExitCode
    }
    catch {
        $record.failure = $_.Exception.ToString()
        throw
    }
    finally {
        try {
            if ($null -ne $job) { $job.Dispose() }
        }
        catch {
            $record.outcome = 'cleanup_failed'
            throw
        }
        finally {
            if ($record.outcome -eq 'running') { $record.outcome = 'failed' }
            [IO.File]::WriteAllText($recordPath, ($record | ConvertTo-Json), [Text.Encoding]::UTF8)
        }
    }
}

function Assert-SoAIStopped {
    param([Parameter(Mandatory=$true)][string]$Root)
    $runtimePython = Resolve-InstalledControlPython -Root $Root
    $source = @'
import logging, os, sys
sys.path.insert(0, sys.argv[2])
from app.updater.soai_instance import is_instance_lock_held, resolve_instance_lock_path
from core.bootstrap.runtime_record_path import resolve_runtime_record_path
from core.runtime.instance_record import read_verified_runtime_instance_record
logger = logging.getLogger('installer.stop')
root = sys.argv[1]
record = read_verified_runtime_instance_record(resolve_runtime_record_path(root, logger=logger), base_dir=root)
if record is not None or is_instance_lock_held(logger=logger, lock_path=resolve_instance_lock_path(base_path=root)):
    raise RuntimeError('The installed application is still running or its instance lock cannot be verified.')
'@
    $backendPath = ConvertTo-RemovalFilesystemPath ($Root.TrimEnd('\') + '\backend')
    $arguments = '-c "' + $source + '" "' + $Root + '" "' + $backendPath + '"'
    $exitCode = Invoke-RemovalControlCommand -Root $Root -Executable $runtimePython -Arguments $arguments -Phase shutdown-verification
    if ($exitCode -ne 0) {
        throw "The installed application shutdown could not be verified. No application files were removed. Diagnostics: $script:removalDiagnosticRoot"
    }
}

function Stop-SoAI {
    param([Parameter(Mandatory=$true)][string]$Root)
    $launcher = Join-Path $Root 'soai.exe'
    if (!(Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $launcher))) {
        return
    }
    Write-Step 'Stopping SoAI...'
    if ([SoAILauncher.NativeBackendJob]::ReleaseInheritedKillOnCloseJobs($Root) -gt 0) {
        Write-Step 'Detached this maintenance from the previous SoAI launcher so closing it cannot interrupt the update.'
    }
    if (![SoAILauncher.ServiceRegistration]::Stop($Root, 300)) {
        Write-Step 'The SoAI background service did not stop within 5 minutes; its processes are stopped directly.'
    }
    $runtimePython = $null
    if (!$InstallerRollback) {
        $runtimePython = Resolve-InstalledControlPython -Root $Root
    }
    $rootPrefix = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $diagnosticParent = [Environment]::GetFolderPath('LocalApplicationData')
    if ([string]::IsNullOrWhiteSpace($diagnosticParent) -or
        ($diagnosticParent.TrimEnd('\') + '\').StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        $diagnosticParent = Join-Path $env:WINDIR 'Temp'
    }
    if (($diagnosticParent.TrimEnd('\') + '\').StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Removal diagnostics require storage outside the installation. No application files were removed.'
    }
    $script:removalDiagnosticRoot = Join-Path $diagnosticParent ('SoAI-Removal-' + [Guid]::NewGuid().ToString('N'))
    $security = New-Object Security.AccessControl.DirectorySecurity
    $security.SetAccessRuleProtection($true, $false)
    $owner = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $security.SetOwner($owner)
    $security.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($owner, [Security.AccessControl.FileSystemRights]::FullControl, [Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit', [Security.AccessControl.PropagationFlags]::None, [Security.AccessControl.AccessControlType]::Allow)))
    [IO.Directory]::CreateDirectory((ConvertTo-RemovalFilesystemPath $script:removalDiagnosticRoot), $security) | Out-Null
    $stopSource = @'
import logging, os, sys
sys.path.insert(0, sys.argv[2])
from app.cli.instance_control import handle_stop
sys.exit(handle_stop(sys.argv[1], logging.getLogger('installer.stop'), expected_edition='soai-core'))
'@
    $backendPath = ConvertTo-RemovalFilesystemPath ($Root.TrimEnd('\') + '\backend')
    $stopArguments = '-P -c "' + $stopSource + '" "' + $Root + '" "' + $backendPath + '"'
    $exitCode = 0
    if ($null -ne $runtimePython) {
        $exitCode = Invoke-RemovalControlCommand -Root $Root -Executable $runtimePython -Arguments $stopArguments -Phase stop
    }
    if ($exitCode -ne 0) {
        Assert-SoAIStopped -Root $Root
    }
    $ownedProcesses = New-Object System.Collections.Generic.List[Diagnostics.Process]
    try {
        foreach ($candidate in [Diagnostics.Process]::GetProcessesByName('soai')) {
            try {
                if ($candidate.HasExited) {
                    $candidate.Dispose()
                    continue
                }
                $null = $candidate.Handle
                $executable = $candidate.MainModule.FileName
                if (![string]::Equals($executable, $launcher, [StringComparison]::OrdinalIgnoreCase)) {
                    $candidate.Dispose()
                    continue
                }
                [void]$ownedProcesses.Add($candidate)
            }
            catch {
                if (!$candidate.HasExited) {
                    $candidate.Dispose()
                    throw
                }
                $candidate.Dispose()
            }
        }
        foreach ($candidate in $ownedProcesses) {
            if (!$candidate.HasExited -and $candidate.MainWindowHandle -ne [IntPtr]::Zero) {
                $null = $candidate.CloseMainWindow()
            }
        }
        foreach ($candidate in $ownedProcesses) {
            Wait-ForOwnedProcessExit -Process $candidate -TimeoutMilliseconds 10000
        }
    }
    finally {
        foreach ($candidate in $ownedProcesses) {
            $candidate.Dispose()
        }
    }
    Stop-InstalledWebViewProcesses -Root $Root
    Stop-InstalledRuntimeProcesses -Root $Root
    $runtimeLockDirectory = $Root.TrimEnd('\') + '\data\state\locks\soai.runtime.lock.d'
    [void][SoAILauncher.NativeFilesystemHandles]::RecoverAbandonedInstallLock($runtimeLockDirectory)
    if ([IO.Directory]::Exists((ConvertTo-RemovalFilesystemPath $runtimeLockDirectory))) {
        throw ('Runtime ownership remains unresolved after shutdown. Diagnostics: ' + $script:removalDiagnosticRoot)
    }
    Remove-Item -LiteralPath (ConvertTo-RemovalFilesystemPath $script:removalDiagnosticRoot) -Recurse -Force -ErrorAction SilentlyContinue
}

function Stop-InstalledRuntimeProcesses {
    param([Parameter(Mandatory=$true)][string]$Root)
    $executables = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($executable in Resolve-InstalledControlPython -Root $Root -All) {
        [void]$executables.Add((ConvertTo-RemovalFilesystemPath $executable))
    }
    $deadline = [Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        $found = $false
        foreach ($name in @('python', 'pythonw')) {
            foreach ($candidate in [Diagnostics.Process]::GetProcessesByName($name)) {
                try {
                    try {
                        if ($candidate.HasExited) { continue }
                        $null = $candidate.Handle
                        $executable = ConvertTo-RemovalFilesystemPath $candidate.MainModule.FileName
                    }
                    catch {
                        if ($candidate.HasExited) { continue }
                        throw
                    }
                    if (!$executables.Contains($executable)) { continue }
                    $found = $true
                    if ($deadline.Elapsed.TotalSeconds -ge 60) {
                        throw "The installed runtime did not finish shutdown. No application files were removed. Diagnostics: $script:removalDiagnosticRoot"
                    }
                    $record = [ordered]@{ phase='runtime-shutdown'; install_root=$Root; process_id=$candidate.Id; executable=$executable }
                    [IO.File]::AppendAllText((ConvertTo-RemovalFilesystemPath ($script:removalDiagnosticRoot + '\runtime-shutdown.log')), ($record | ConvertTo-Json -Compress) + [Environment]::NewLine, [Text.Encoding]::UTF8)
                    Wait-ForOwnedProcessExit -Process $candidate -TimeoutMilliseconds 1000
                }
                finally { $candidate.Dispose() }
            }
        }
        if (!$found) { return }
    }
}

function Wait-ForOwnedProcessExit {
    param(
        [Parameter(Mandatory=$true)][Diagnostics.Process]$Process,
        [Parameter(Mandatory=$true)][int]$TimeoutMilliseconds
    )
    if ($Process.WaitForExit($TimeoutMilliseconds)) {
        return
    }
    if (!$Process.HasExited) {
        $Process.Kill()
    }
    if (!$Process.WaitForExit(10000)) {
        throw 'An owned SoAI process could not be stopped. No application files were removed.'
    }
}

function Stop-InstalledWebViewProcesses {
    param([Parameter(Mandatory=$true)][string]$Root)
    $rootPrefix = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $deadline = [Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        $views = [Diagnostics.Process]::GetProcessesByName('msedgewebview2')
        $potentialViews = $views.Count
        foreach ($view in $views) { $view.Dispose() }
        if ($potentialViews -eq 0) { return }
        $found = $false
        foreach ($instance in @(Get-CimInstance -ClassName Win32_Process -Filter "Name = 'msedgewebview2.exe'" -ErrorAction SilentlyContinue)) {
            if ([string]::IsNullOrEmpty($instance.CommandLine) -or $instance.CommandLine.IndexOf($rootPrefix, [StringComparison]::OrdinalIgnoreCase) -lt 0) { continue }
            try { $candidate = [Diagnostics.Process]::GetProcessById([int]$instance.ProcessId) }
            catch [ArgumentException] { continue }
            try {
                try {
                    if ($candidate.HasExited -or [Math]::Abs(($candidate.StartTime - $instance.CreationDate).TotalSeconds) -ge 1) { continue }
                }
                catch {
                    if ($candidate.HasExited) { continue }
                    throw
                }
                $found = $true
                if ($deadline.Elapsed.TotalSeconds -ge 60) {
                    throw 'The SoAI desktop view did not finish shutdown. No application files were removed.'
                }
                Wait-ForOwnedProcessExit -Process $candidate -TimeoutMilliseconds 10000
            }
            finally { $candidate.Dispose() }
        }
        if (!$found) { return }
    }
}

function Remove-FileIfPresent {
    param([Parameter(Mandatory=$true)][string]$Path)
    if (Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $Path) -PathType Leaf) {
        Remove-Item -LiteralPath (ConvertTo-RemovalFilesystemPath $Path) -Force -ErrorAction Stop
        if (Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $Path) -PathType Leaf) {
            throw "Failed to remove file: $Path"
        }
    }
}

function Remove-AdmittedApplicationData {
    param([Parameter(Mandatory=$true)][string]$DataRoot)
    $root = [IO.Path]::GetFullPath($DataRoot).TrimEnd('\')
    $lockDirectory = [IO.Path]::GetFullPath($env:SOAI_INSTALL_LOCK_HELD_PATH).TrimEnd('\')
    $expectedLockDirectory = $root + '\state\locks\soai.install.lock.d'
    if (![string]::Equals($lockDirectory, $expectedLockDirectory, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The data cleanup does not match the installer admission owner.'
    }
    Assert-RemovalAdmissionOwner -LockDirectory $lockDirectory
    Remove-DirectoryEntries -Directory $root -ProtectedPaths @($lockDirectory, ($root + '\locks\soai.installation.transaction.lock'))
}

function Remove-DirectoryEntries {
    param(
        [Parameter(Mandatory=$true)][string]$Directory,
        [string[]]$ProtectedPaths = @()
    )
    $nativeDirectory = ConvertTo-RemovalFilesystemPath $Directory
    foreach ($entry in [IO.Directory]::GetFileSystemEntries($nativeDirectory)) {
        $logicalEntry = $Directory.TrimEnd('\') + '\' + [IO.Path]::GetFileName($entry)
        $protected = $false
        $containsProtectedPath = $false
        foreach ($protectedPath in $ProtectedPaths) {
            if ([string]::Equals($logicalEntry, $protectedPath, [StringComparison]::OrdinalIgnoreCase)) { $protected = $true }
            if ($protectedPath.StartsWith($logicalEntry + '\', [StringComparison]::OrdinalIgnoreCase)) { $containsProtectedPath = $true }
        }
        if ($protected) { continue }
        $attributes = [IO.File]::GetAttributes($entry)
        $isDirectory = ($attributes -band [IO.FileAttributes]::Directory) -ne 0
        $isReparsePoint = ($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
        if ($containsProtectedPath) {
            if (!$isDirectory -or $isReparsePoint) { throw 'An admission ancestor changed during data cleanup.' }
            Remove-DirectoryEntries -Directory $logicalEntry -ProtectedPaths $ProtectedPaths
        }
        elseif ($isDirectory -and !$isReparsePoint) {
            Remove-DirectoryEntries -Directory $logicalEntry -ProtectedPaths $ProtectedPaths
            [IO.Directory]::Delete($entry, $false)
        }
        elseif ($isDirectory) { [IO.Directory]::Delete($entry, $false) }
        else {
            if (!$isReparsePoint -and ($attributes -band [IO.FileAttributes]::ReadOnly) -ne 0) {
                [IO.File]::SetAttributes($entry, $attributes -band (-bnot [IO.FileAttributes]::ReadOnly))
            }
            [IO.File]::Delete($entry)
        }
    }
}

function Resolve-UnlinkedDirectory {
    param(
        [Parameter(Mandatory=$true)][string]$Directory,
        [Parameter(Mandatory=$true)][string[]]$Components
    )
    $current = $Directory.TrimEnd('\')
    foreach ($component in $Components) {
        $current = $current + '\' + $component
        $nativeCurrent = ConvertTo-RemovalFilesystemPath $current
        if (![IO.Directory]::Exists($nativeCurrent)) { return $null }
        if (([IO.File]::GetAttributes($nativeCurrent) -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            Write-Step "Per-user SoAI data behind a link was not removed: $current"
            return $null
        }
    }
    return $current
}

function Remove-UserLauncherState {
    param([Parameter(Mandatory=$true)][string]$Root)
    $identity = [SoAILauncher.LauncherPaths]::StableRootIdentity($Root)
    $profileList = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine, [Microsoft.Win32.RegistryView]::Registry64)
    try {
        $profiles = $profileList.OpenSubKey('SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList')
        if ($null -eq $profiles) { throw 'The Windows profile list is unavailable; per-user SoAI data was not removed.' }
        try {
            foreach ($sid in $profiles.GetSubKeyNames()) {
                $profileKey = $profiles.OpenSubKey($sid)
                if ($null -eq $profileKey) { continue }
                try { $profilePath = [Environment]::ExpandEnvironmentVariables([string]$profileKey.GetValue('ProfileImagePath', '')) }
                finally { $profileKey.Dispose() }
                if ([string]::IsNullOrWhiteSpace($profilePath) -or ![IO.Path]::IsPathRooted($profilePath)) { continue }
                $stateDirectory = Resolve-UnlinkedDirectory -Directory $profilePath -Components @('AppData', 'Local', 'SoAI')
                if ($null -eq $stateDirectory) { continue }
                $browserProfile = Resolve-UnlinkedDirectory -Directory $stateDirectory -Components @('launcher-webview2', $identity)
                if ($null -ne $browserProfile) {
                    Write-Step "Removing per-user SoAI data from $browserProfile..."
                    Stop-InstalledWebViewProcesses -Root $browserProfile
                    Remove-DirectoryEntries -Directory $browserProfile
                    [IO.Directory]::Delete((ConvertTo-RemovalFilesystemPath $browserProfile), $false)
                }
                $browserProfiles = $stateDirectory + '\launcher-webview2'
                if ([IO.Directory]::Exists((ConvertTo-RemovalFilesystemPath $browserProfiles)) -and
                    [IO.Directory]::GetFileSystemEntries((ConvertTo-RemovalFilesystemPath $browserProfiles)).Count -gt 0) {
                    continue
                }
                Write-Step "Removing per-user SoAI data from $stateDirectory..."
                foreach ($candidate in [Diagnostics.Process]::GetProcessesByName('soai')) {
                    try {
                        try {
                            if ($candidate.HasExited) { continue }
                            $null = $candidate.Handle
                            $executable = $candidate.MainModule.FileName
                        }
                        catch {
                            if ($candidate.HasExited) { continue }
                            throw
                        }
                        if ($executable.StartsWith($stateDirectory + '\', [StringComparison]::OrdinalIgnoreCase)) {
                            Wait-ForOwnedProcessExit -Process $candidate -TimeoutMilliseconds 10000
                        }
                    }
                    finally { $candidate.Dispose() }
                }
                Stop-InstalledWebViewProcesses -Root $stateDirectory
                Remove-DirectoryEntries -Directory $stateDirectory
                [IO.Directory]::Delete((ConvertTo-RemovalFilesystemPath $stateDirectory), $false)
            }
        }
        finally { $profiles.Dispose() }
    }
    finally { $profileList.Dispose() }
}

function Remove-DirectoryTree {
    param([Parameter(Mandatory=$true)][string]$Path)
    if ($env:SOAI_INSTALL_LOCK_HELD_PATH -and
        [string]::Equals([IO.Path]::GetFullPath($Path).TrimEnd('\'), (Join-Path $root 'data').TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
        Remove-AdmittedApplicationData -DataRoot $Path
        return
    }
    for ($attempt = 0; $attempt -lt 3 -and (Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $Path) -PathType Container); $attempt++) {
        if ($attempt -gt 0) { Start-Sleep -Seconds 1 }
        Remove-Item -LiteralPath (ConvertTo-RemovalFilesystemPath $Path) -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $Path) -PathType Container) {
        throw "Failed to remove directory tree: $Path"
    }
}

function Remove-DirectoryIfPresent {
    param([Parameter(Mandatory=$true)][string]$Path)
    Remove-DirectoryTree -Path $Path
}

function Remove-SourceBytecode {
    param([Parameter(Mandatory=$true)][string]$SourcePath)
    if ([IO.Path]::GetExtension($SourcePath) -notin @('.py', '.pyw')) {
        return
    }
    $cachePath = Join-Path ([IO.Path]::GetDirectoryName($SourcePath)) '__pycache__'
    if (!(Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $cachePath))) {
        return
    }
    $cacheDirectory = Get-Item -LiteralPath (ConvertTo-RemovalFilesystemPath $cachePath) -Force -ErrorAction Stop
    if (!$cacheDirectory.PSIsContainer -or
        ($cacheDirectory.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The Python bytecode cache is not a regular directory; source replacement was refused.'
    }
    $moduleName = [Regex]::Escape([IO.Path]::GetFileNameWithoutExtension($SourcePath))
    $cachePattern = '^' + $moduleName + '\.[^.]+(?:\.opt-[^.]+)?\.pyc$'
    foreach ($entry in Get-ChildItem -LiteralPath (ConvertTo-RemovalFilesystemPath $cachePath) -Force -ErrorAction Stop) {
        if ($entry.Name -notmatch $cachePattern) {
            continue
        }
        if ($entry.PSIsContainer -or
            ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'A Python bytecode cache entry is not a regular file; source replacement was refused.'
        }
        Remove-FileIfPresent -Path $entry.FullName
    }
}

function Preserve-InstallationDiagnostics {
    param([Parameter(Mandatory=$true)][string]$Root)
    $support = Resolve-ChildPath -Root $Root -Child 'installer-support'
    $nativeSupport = ConvertTo-RemovalFilesystemPath $support
    if (![IO.Directory]::Exists($nativeSupport)) { return }
    Retain-RemovalDirectory -Path $support
    $archives = @([IO.DirectoryInfo]::new($nativeSupport).GetFileSystemInfos('install-diagnostics-*.zip'))
    if ($archives.Count -eq 0) { return }
    foreach ($archive in $archives) {
        if (($archive.Attributes -band ([IO.FileAttributes]::Directory -bor [IO.FileAttributes]::ReparsePoint)) -ne 0) {
            throw 'An installation diagnostic archive is not a regular file. No diagnostic archives were moved.'
        }
    }
    $destination = Resolve-ChildPath -Root $Root -Child 'data\installer-diagnostics'
    $nativeDestination = ConvertTo-RemovalFilesystemPath $destination
    [IO.Directory]::CreateDirectory($nativeDestination) | Out-Null
    Retain-RemovalDirectory -Path $destination
    foreach ($archive in $archives) {
        $target = $nativeDestination + '\' + $archive.Name
        $attributes = [SoAILauncher.NativeFilesystemHandles]::GetFileAttributes($target)
        $failure = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        if ($attributes -ne [uint32]::MaxValue) {
            throw "An installation diagnostic retention target already exists: $($archive.Name). No diagnostic archives were moved."
        }
        if ($failure -ne 2 -and $failure -ne 3) {
            throw (New-Object ComponentModel.Win32Exception($failure, 'An installation diagnostic retention target could not be verified. No diagnostic archives were moved.'))
        }
    }
    foreach ($archive in $archives) {
        [IO.File]::Move($archive.FullName, ($nativeDestination + '\' + $archive.Name))
    }
}

function Remove-ManifestFiles {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [string]$ExplicitManifestPath = '',
        [switch]$PreserveApplicationData
    )
    $manifest = if ([string]::IsNullOrWhiteSpace($ExplicitManifestPath)) {
        Join-Path $Root 'installer-support\installed-files.txt'
    }
    else {
        Resolve-FullPath $ExplicitManifestPath
    }
    if (!(Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $manifest))) {
        if (![string]::IsNullOrWhiteSpace($ExplicitManifestPath)) {
            throw "The required SoAI cleanup manifest is missing: $manifest"
        }
        return
    }
    $dataRoot = Resolve-ChildPath -Root $Root -Child 'data'
    $dataPrefix = $dataRoot.TrimEnd('\') + '\'
    $installRootMarker = Resolve-ChildPath -Root $Root -Child '.soai-install-root'
    $removalScript = Resolve-ChildPath -Root $Root -Child 'installer-support\Remove-SoAI.ps1'
    $ownershipScript = Resolve-ChildPath -Root $Root -Child 'installer-support\Shared-SoAIResourceOwnership.ps1'
    foreach ($line in Get-Content -LiteralPath (ConvertTo-RemovalFilesystemPath $manifest)) {
        $relative = ''
        if ($line -ne $null) {
            $relative = $line.Trim()
        }
        if ($relative.Length -eq 0) {
            continue
        }
        $target = Resolve-ChildPath -Root $Root -Child $relative
        if ($Mode -eq 'Uninstall' -and $env:SOAI_UNINSTALL_OWNER_PID -and
            [string]::Equals($target, $installRootMarker, [StringComparison]::OrdinalIgnoreCase)) {
            continue
        }
        if ($PreserveApplicationData -and
            ([string]::Equals($target, $dataRoot, [StringComparison]::OrdinalIgnoreCase) -or
            $target.StartsWith($dataPrefix, [StringComparison]::OrdinalIgnoreCase) -or
            [string]::Equals($target, $installRootMarker, [StringComparison]::OrdinalIgnoreCase) -or
            [string]::Equals($target, $manifest, [StringComparison]::OrdinalIgnoreCase) -or
            [string]::Equals($target, $removalScript, [StringComparison]::OrdinalIgnoreCase) -or
            [string]::Equals($target, $ownershipScript, [StringComparison]::OrdinalIgnoreCase))) {
            continue
        }
        if ($Mode -eq 'Upgrade' -and
            [string]::Equals($target, (Join-Path $Root 'soai.exe'), [StringComparison]::OrdinalIgnoreCase)) {
            continue
        }
        Remove-SourceBytecode -SourcePath $target
        Remove-FileIfPresent $target
    }
}

function Remove-Shortcuts {
    param([Parameter(Mandatory=$true)][string]$Root)
    if (![SoAILauncher.SynchronousUninstall]::OwnsWindowsIntegration($Root)) { return }
    $shortcutDirs = @(
        [Environment]::GetFolderPath('CommonDesktopDirectory'),
        [Environment]::GetFolderPath('DesktopDirectory'),
        [Environment]::GetFolderPath('CommonPrograms'),
        [Environment]::GetFolderPath('Programs')
    ) | Where-Object { $_ }
    foreach ($dir in $shortcutDirs) {
        Remove-FileIfPresent (Join-Path $dir 'SoAI.lnk')
        Remove-DirectoryIfPresent (Join-Path $dir 'SoAI')
    }
}

function Remove-EmptyDirectories {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [string]$PreservedRoot = ''
    )
    if (!$Root.StartsWith('\\?\', [StringComparison]::Ordinal)) {
        if ($Root.StartsWith('\\', [StringComparison]::Ordinal)) {
            $Root = '\\?\UNC\' + $Root.Substring(2)
        }
        else {
            $Root = '\\?\' + $Root
        }
    }
    if (![string]::IsNullOrWhiteSpace($PreservedRoot) -and
        !$PreservedRoot.StartsWith('\\?\', [StringComparison]::Ordinal)) {
        if ($PreservedRoot.StartsWith('\\', [StringComparison]::Ordinal)) {
            $PreservedRoot = '\\?\UNC\' + $PreservedRoot.Substring(2)
        }
        else {
            $PreservedRoot = '\\?\' + $PreservedRoot
        }
    }
    if (!(Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $Root) -PathType Container)) {
        return
    }
    foreach ($directory in Get-ChildItem -LiteralPath (ConvertTo-RemovalFilesystemPath $Root) -Directory -Force -ErrorAction Stop) {
        if ((![string]::IsNullOrWhiteSpace($PreservedRoot) -and
            [string]::Equals($directory.FullName, $PreservedRoot, [StringComparison]::OrdinalIgnoreCase)) -or
            (Test-RetainedUpdateStorageName -EntryName $directory.Name) -or
            ($directory.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            continue
        }
        Remove-EmptyDirectories -Root $directory.FullName -PreservedRoot $PreservedRoot
        if (!(Get-ChildItem -LiteralPath (ConvertTo-RemovalFilesystemPath $directory.FullName) -Force -ErrorAction Stop)) {
            Remove-Item -LiteralPath (ConvertTo-RemovalFilesystemPath $directory.FullName) -Force -ErrorAction Stop
        }
    }
}

function Remove-InstallRootIfEmpty {
    param([Parameter(Mandatory=$true)][string]$Root)
    if (!(Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $Root) -PathType Container)) {
        return
    }

    $remaining = @(Get-ChildItem -LiteralPath (ConvertTo-RemovalFilesystemPath $Root) -Force -ErrorAction Stop)
    if ($remaining.Count -gt 0) {
        $names = ($remaining | Select-Object -First 8 -ExpandProperty Name) -join ', '
        if ($remaining.Count -gt 8) {
            $names = "$names, ..."
        }
        throw "SoAI cleanup left files in ${Root}: $names"
    }

    Remove-Item -LiteralPath (ConvertTo-RemovalFilesystemPath $Root) -Force -ErrorAction Stop
    if (Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $Root) -PathType Container) {
        throw "Failed to remove empty SoAI install directory: $Root"
    }
}

$script:removalGate = $null
$script:removalTransaction = $null
$script:removalOwnedLock = ''
$script:removalToken = ''
$script:removalComplete = $false
$script:removalHandles = New-Object System.Collections.Generic.List[Microsoft.Win32.SafeHandles.SafeFileHandle]
$previousLockPath = $env:SOAI_INSTALL_LOCK_HELD_PATH
$previousLockToken = $env:SOAI_INSTALL_LOCK_HELD_TOKEN
$previousOwnerStarted = $env:SOAI_INSTALL_LOCK_OWNER_START_MS
if ($Mode -eq 'VerifyUninstall') {
    $verificationRoot = [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($ControlLauncherPath))
    if ([string]::IsNullOrWhiteSpace($VerificationPath) -or
        ![string]::Equals([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($VerificationPath)), $verificationRoot, [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName($VerificationPath) -cnotmatch '^verified-[0-9a-f]{32}\.txt$') {
        throw 'Uninstall verification requires an owned completion record beside its control launcher.'
    }
    [Reflection.Assembly]::Load([IO.File]::ReadAllBytes((ConvertTo-RemovalFilesystemPath $ControlLauncherPath))) | Out-Null
    Assert-SoAISharedResourceRelease -InstallRoot $InstallRoot -RetainData (!$RemoveApplicationData)
    $selection = if ($RemoveApplicationData) { 'all' } else { 'retain' }
    [SoAILauncher.NativeFilesystemHandles]::WriteNewDurableFile($VerificationPath, ($selection + "`n" + [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')))
    return
}
try {
    $root = Assert-SafeInstallRoot $InstallRoot -DeferRetainedUpdateCheck
    if ($RemoveApplicationData -and $Mode -notin @('Uninstall', 'ArchiveUninstall')) {
        throw 'Application data removal is valid only for an uninstall operation.'
    }
    if ($InstallerRollback -and $Mode -ne 'Upgrade' -and !($Mode -eq 'Uninstall' -and $RemoveApplicationData)) {
        throw 'Installer rollback removal is valid only for restoring an upgrade or removing a failed fresh installation.'
    }
    Initialize-RemovalAdmission -Root $root
    $null = Assert-SafeInstallRoot -Root $root -DeferRetainedUpdateCheck:($RemoveApplicationData -and $Mode -in @('Uninstall', 'ArchiveUninstall'))
    Stop-SoAI -Root $root

    $updateStoragePresent = @([IO.Directory]::GetFileSystemEntries((ConvertTo-RemovalFilesystemPath $root)) | Where-Object { Test-RetainedUpdateStorageName -EntryName ([IO.Path]::GetFileName($_)) }).Count -gt 0
    if ($RemoveApplicationData -and $Mode -in @('Uninstall', 'ArchiveUninstall') -and $updateStoragePresent) {
        $python = Resolve-InstalledControlPython -Root $root
        $disposal = @'
import sys
from app.updater.software_update.committed_transaction_disposal import dispose_update_transaction_for_all_data_uninstall
from core.logging.trace import get_logger
dispose_update_transaction_for_all_data_uninstall(sys.argv[1], get_logger('SoAI.installer.uninstall_disposal'), edition='soai-core')
'@
        $priorPythonPath = $env:PYTHONPATH
        $priorBytecode = $env:PYTHONDONTWRITEBYTECODE
        try {
            $env:PYTHONPATH = Join-Path $root 'backend'
            $env:PYTHONDONTWRITEBYTECODE = '1'
            & $python -B -P -c $disposal $root | Out-Host
            if ($LASTEXITCODE -ne 0) { throw 'All-data uninstall could not dispose its owned update transaction. Recovery evidence has been retained.' }
        }
        finally {
            $env:PYTHONPATH = $priorPythonPath
            $env:PYTHONDONTWRITEBYTECODE = $priorBytecode
        }
        $null = Assert-SafeInstallRoot -Root $root
    }

    if ($Mode -eq 'Stop') {
        return
    }

    if ($Mode -eq 'Upgrade') {
        Write-Step 'Removing files from the previous SoAI install manifest...'
        Remove-FileIfPresent (Join-Path $root 'installer-support\.soai-launcher.pending')
        Remove-ManifestFiles -Root $root -ExplicitManifestPath $ManifestPath
        Remove-DirectoryIfPresent (Join-Path $root 'webview2')
        Remove-EmptyDirectories -Root $root
        return
    }

    $preserveApplicationData = $Mode -in @('Uninstall', 'ArchiveUninstall') -and !$RemoveApplicationData
    if ($preserveApplicationData) {
        Preserve-InstallationDiagnostics -Root $root
    }
    $releaseJournal = ''
    if ($Mode -eq 'Uninstall' -and $RemoveApplicationData -and $env:SOAI_UNINSTALL_OWNER_PID) {
        $releaseStage = [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($ControlLauncherPath))
        if (![string]::Equals($releaseStage, $PSScriptRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'The shared ownership release journal is outside the protected uninstall staging directory.'
        }
        $releaseJournal = Join-Path $releaseStage 'shared-release.txt'
    }
    Release-SoAISharedResourceClaim -InstallRoot $root -RetainData (!$RemoveApplicationData) -ReleaseJournalPath $releaseJournal

    if ([SoAILauncher.ServiceRegistration]::Unregister($root)) {
        Write-Step 'Removed the SoAI background service.'
    }
    if ($RemoveApplicationData -and !$InstallerRollback) {
        Remove-UserLauncherState -Root $root
    }
    if ($preserveApplicationData) {
        Write-Step 'Removing SoAI application files while retaining application data...'
    }
    else {
        Write-Step 'Removing SoAI application files and application data...'
    }
    if ($Mode -eq 'Uninstall') {
        Remove-Shortcuts -Root $root
    }
    $installedManifest = if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
        Join-Path $root 'installer-support\installed-files.txt'
    }
    else {
        Resolve-FullPath $ManifestPath
    }
    if (!$preserveApplicationData -and $env:SOAI_INSTALL_LOCK_HELD_PATH) {
        Remove-DirectoryIfPresent (Resolve-ChildPath -Root $root -Child 'data')
    }
    Remove-ManifestFiles -Root $root -ExplicitManifestPath $ManifestPath -PreserveApplicationData:$preserveApplicationData
    $ownedDirectories = @(
        'backend',
        'frontend',
        'plugins',
        'licenses',
        'python',
        'python-3.13',
        'runtime',
        'soai_main_venv',
        'soai_python',
        'webview2'
    )
    if (!$preserveApplicationData) {
        $ownedDirectories += @('installer-support')
        if (!$env:SOAI_INSTALL_LOCK_HELD_PATH) { $ownedDirectories += @('data') }
    }
    foreach ($relative in $ownedDirectories) {
        Remove-DirectoryIfPresent (Resolve-ChildPath -Root $root -Child $relative)
    }

    $ownedFiles = @(
        '.soai_install_manifest.json',
        '.soai_install_in_progress',
        'soai.exe',
        'soai.exe.config',
        'Uninstall.exe',
        'Uninstall.exe.config',
        'installer-support\UninstallWorker.exe',
        'soai-app.ico',
        'install_soai_from_release.bat',
        'CHANGE-DATES.md',
        'COMMERCIAL-LICENSE.md',
        'COMMERCIAL-LICENSING-AVAILABILITY.md',
        'COMMERCIAL-SUPPORT-TERMS.md',
        'ORGANIZATION-EVALUATION-TERMS.md',
        'install-soai-from-release.bat',
        'install-soai-from-release.command',
        'install-soai-from-release.sh',
        'install-soai-linux.sh',
        'install-soai-macos.command',
        'install-soai-windows.ps1',
        'uninstall-soai-linux.sh',
        'requirements.txt',
        'README.md',
        'LICENSE.md',
        'LICENSING.md',
        'ORGANIZATION_EVALUATION_TERMS.md',
        'PERSONAL-PURCHASE-TERMS.md',
        'NOTICE',
        'DOCUMENTATION.md',
        'COMMERCIAL_LICENSING_AVAILABILITY.md',
        'COMMERCIAL_LICENSE.md',
        'COMMERCIAL_SUPPORT_TERMS.md',
        'Microsoft.Web.WebView2.Core.dll',
        'Microsoft.Web.WebView2.WinForms.dll',
        'WebView2Loader.dll',
        'msvcp140.dll',
        'msvcp140_1.dll',
        'msvcp140_2.dll',
        'msvcp140_atomic_wait.dll',
        'msvcp140_codecvt_ids.dll',
        'vcruntime140.dll',
        'vcruntime140_1.dll'
    )
    if (!$preserveApplicationData -and !($Mode -eq 'Uninstall' -and $env:SOAI_UNINSTALL_OWNER_PID)) {
        $ownedFiles += '.soai-install-root'
    }
    foreach ($relative in $ownedFiles) {
        Remove-FileIfPresent (Resolve-ChildPath -Root $root -Child $relative)
    }

    if ($preserveApplicationData) {
        $retainedMarker = Join-Path $root '.soai-install-root'
        if (!(Test-Path -LiteralPath (ConvertTo-RemovalFilesystemPath $retainedMarker))) {
            [IO.File]::WriteAllText((ConvertTo-RemovalFilesystemPath $retainedMarker), 'SoAI Windows Installer Root')
        }
        $retainedManifest = Join-Path $root 'installer-support\installed-files.txt'
        if (![string]::Equals($installedManifest, $retainedManifest, [StringComparison]::OrdinalIgnoreCase)) {
            [IO.Directory]::CreateDirectory((ConvertTo-RemovalFilesystemPath ([IO.Path]::GetDirectoryName($retainedManifest)))) | Out-Null
            [IO.File]::Copy((ConvertTo-RemovalFilesystemPath $installedManifest), (ConvertTo-RemovalFilesystemPath $retainedManifest), $true)
        }
        Remove-EmptyDirectories -Root $root -PreservedRoot (Join-Path $root 'data')
        Write-Step "SoAI application data was retained at $(Join-Path $root 'data')."
    }
    else {
        Remove-EmptyDirectories -Root $root
        if ($env:SOAI_INSTALL_LOCK_HELD_PATH) {
            $remaining = @(Get-ChildItem -LiteralPath (ConvertTo-RemovalFilesystemPath $root) -Force -ErrorAction Stop)
            foreach ($entry in $remaining) {
                if (![string]::Equals($entry.Name, 'data', [StringComparison]::OrdinalIgnoreCase) -and
                    !($Mode -eq 'Uninstall' -and $env:SOAI_UNINSTALL_OWNER_PID -and $entry.Name -ceq '.soai-install-root')) {
                    throw "Admitted cleanup retained an unexpected application entry: $($entry.Name)"
                }
            }
        }
        else {
            Remove-InstallRootIfEmpty -Root $root
        }
    }
    $script:removalComplete = $true
} finally {
    try {
        if ($script:removalOwnedLock -and $script:removalToken) {
            Assert-RemovalAdmissionOwner -LockDirectory $script:removalOwnedLock
            $lockHandle = $script:removalHandles[$script:removalHandles.Count - 1]
            $lockHandle.Dispose()
            $script:removalHandles.RemoveAt($script:removalHandles.Count - 1)
            Assert-RemovalAdmissionOwner -LockDirectory $script:removalOwnedLock
            $nativeLock = ConvertTo-RemovalFilesystemPath $script:removalOwnedLock
            [IO.File]::Delete($nativeLock + '\pid')
            [IO.File]::Delete($nativeLock + '\token')
            [IO.File]::Delete($nativeLock + '\owner-start-ms')
            [IO.Directory]::Delete($nativeLock, $false)
        }
    } finally {
        try {
            if ($null -ne $script:removalTransaction) { $script:removalTransaction.Dispose() }
            for ($index = $script:removalHandles.Count - 1; $index -ge 0; $index -= 1) {
                $script:removalHandles[$index].Dispose()
            }
            if ($script:removalOwnedLock -and $script:removalComplete -and $RemoveApplicationData) {
                $nativeRoot = ConvertTo-RemovalFilesystemPath $root
                [IO.File]::Delete($nativeRoot + '\data\locks\soai.installation.transaction.lock')
                foreach ($relative in @('data\state\locks', 'data\state', 'data\locks', 'data')) {
                    [IO.Directory]::Delete($nativeRoot + '\' + $relative, $false)
                }
                [IO.Directory]::Delete($nativeRoot, $false)
            }
        } finally {
            $env:SOAI_INSTALL_LOCK_HELD_PATH = $previousLockPath
            $env:SOAI_INSTALL_LOCK_HELD_TOKEN = $previousLockToken
            $env:SOAI_INSTALL_LOCK_OWNER_START_MS = $previousOwnerStarted
            if ($null -ne $script:removalGate) { $script:removalGate.Dispose() }
        }
    }
}
if ($script:removalComplete) { Write-Step 'SoAI uninstall cleanup completed.' }
