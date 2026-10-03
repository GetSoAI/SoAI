# SoAI - Windows target and accepted-update admission [installer/scripts/Admit-SoAIInstall.ps1]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InstallRoot,
    [Parameter(Mandatory=$true)][string]$CandidateConfigPath,
    [Parameter(Mandatory=$true)][string]$CandidateVersion,
    [Parameter(Mandatory=$true)][string]$ClassificationPath,
    [string]$CandidateLauncherPath = '',
    [ValidateSet('Target','Transactions')][string]$Mode = 'Target'
)

$ErrorActionPreference = 'Stop'
trap { if ($env:SOAI_INSTALLER_FAILURE_PATH) { try { [IO.File]::WriteAllText($env:SOAI_INSTALLER_FAILURE_PATH, (($_.Exception.Message -replace '\s+', ' ').Trim()), [Text.Encoding]::Unicode) } catch { } }; break }
$root = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
$volume = [IO.Path]::GetPathRoot($root)
if ([string]::Equals($root, $volume.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The installation target must not be a volume root.'
}
if ($root.IndexOfAny([char[]]"`0`r`n`t") -ge 0) {
    throw 'The installation target exceeds the supported path capacity or contains control characters.'
}
$relative = $root.Substring($volume.Length)
foreach ($component in $relative.Split('\')) {
    if ($component.Length -eq 0 -or $component.Length -gt 255 -or
        $component.EndsWith('.') -or $component.EndsWith(' ') -or
        $component.IndexOfAny([IO.Path]::GetInvalidFileNameChars()) -ge 0 -or
        $component -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)') {
        throw 'The installation target contains an unsupported Windows path component.'
    }
}
function ConvertTo-InstallerFilesystemPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    if ($Path.StartsWith('\\?\', [StringComparison]::Ordinal)) { return $Path }
    if ($Path.StartsWith('\\', [StringComparison]::Ordinal)) { return '\\?\UNC\' + $Path.Substring(2) }
    return '\\?\' + $Path
}
$current = $root
while ($current) {
    $nativePath = ConvertTo-InstallerFilesystemPath $current
    if ([IO.File]::Exists($nativePath)) { throw 'The installation target has a file ancestor.' }
    if ([IO.Directory]::Exists($nativePath)) {
        $attributes = [IO.File]::GetAttributes($nativePath)
        if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'The installation target has a reparse-point ancestor.'
        }
    }
    if ([string]::Equals($current, $volume.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) { break }
    $parent = [IO.Path]::GetDirectoryName($current)
    if ($parent -eq $current) { break }
    $current = $parent
}
$nativeRoot = ConvertTo-InstallerFilesystemPath $root
$classification = 'fresh'
if ($Mode -eq 'Target' -and [IO.Directory]::Exists($nativeRoot) -and [IO.Directory]::GetFileSystemEntries($nativeRoot).Length -gt 0) {
    if (![IO.File]::Exists($nativeRoot + '\.soai-install-root') -and
        ![IO.File]::Exists($nativeRoot + '\.soai_install_manifest.json') -and
        !([IO.File]::Exists($nativeRoot + '\soai.exe') -and [IO.File]::Exists($nativeRoot + '\backend\main.py'))) {
        throw 'The nonempty installation target is not a recognizable SoAI installation.'
    }
    $classification = 'existing'
}
foreach ($metadata in @('.soai_install_manifest.json', 'release-info-v1.json')) {
    $path = $nativeRoot + '\' + $metadata
    if ([IO.File]::Exists($path)) {
        $identity = [IO.File]::ReadAllText($path) | ConvertFrom-Json
        if ($identity.schema_version -ne 1 -or $identity.product -cne 'SoAI' -or $identity.edition -cne 'soai-core') {
            throw 'The existing installation identity is invalid or belongs to another edition.'
        }
    }
}
if ([IO.File]::Exists($nativeRoot + '\data\state\backup_restore_journal.json')) {
    throw 'An unfinished backup restore requires recovery before installation.'
}
$transactions = @()
if ([IO.Directory]::Exists($nativeRoot)) {
    $transactions = @([IO.Directory]::GetFileSystemEntries($nativeRoot) | Where-Object {
        [IO.Path]::GetFileName($_).StartsWith('.soai_update_transaction_', [StringComparison]::Ordinal) -or
        [IO.Path]::GetFileName($_).StartsWith('.soai_update_cleanup_', [StringComparison]::Ordinal)
    })
}
if ($transactions.Count -gt 0) {
    if ($transactions.Count -ne 1 -or ![IO.Path]::GetFileName($transactions[0]).StartsWith('.soai_update_transaction_', [StringComparison]::Ordinal)) {
        throw 'An unfinished software update requires verified recovery before installation.'
    }
    $transaction = $transactions[0].Substring($nativeRoot.Length)
    $transaction = $root + $transaction
    $python = $transactions[0] + '\recovery_runtime\python.exe'
    $backend = $transaction + '\old\backend'
    if (![IO.File]::Exists($python) -or ![IO.Directory]::Exists((ConvertTo-InstallerFilesystemPath $backend))) {
        throw 'The retained update verification runtime is missing.'
    }
    $verification = @'
import os
import sys
from app.updater.software_update.recovery_bootstrap import resolve_update_recovery_package_paths
sys.path.extend(resolve_update_recovery_package_paths(sys.argv[1]))
import psutil
from app.updater.software_update.activation_state import read_update_activation_identity, validate_update_recovery_evidence
from app.updater.software_update.install_transaction_state import paths_from_transaction_directory, marker_path
from app.updater.software_update.update_lock import resolve_software_update_lock_dir, require_software_update_lock_owner
from core.runtime.instance_record import read_runtime_instance_record
base, transaction, version = sys.argv[1:]
paths = paths_from_transaction_directory(base, transaction)
validate_update_recovery_evidence(paths)
identity = read_update_activation_identity(paths)
if identity.edition != 'soai-core' or identity.to_version != version:
    raise RuntimeError('The setup does not match the accepted update identity.')
lock = resolve_software_update_lock_dir(base)
owner = read_runtime_instance_record(os.path.join(lock, 'process.json'))
require_software_update_lock_owner(lock, base_path=base, edition='soai-core', expected_pid=owner.pid)
if not any(parent.pid == owner.pid and int(round(parent.create_time() * 1_000_000_000)) == owner.process_create_time_ns for parent in psutil.Process().parents()):
    raise RuntimeError('The setup is not a child of the verified update owner.')
if not os.path.isfile(marker_path(transaction, 'old_complete')) or not os.path.isfile(marker_path(transaction, 'rollback_required')):
    raise RuntimeError('The update is not armed for native replacement.')
if any(os.path.lexists(marker_path(transaction, marker)) for marker in ('new_complete', 'success_complete', 'activation_failed', 'rollback_complete')):
    raise RuntimeError('The update is no longer eligible for native replacement.')
'@
    $priorPythonPath = $env:PYTHONPATH
    $priorBytecode = $env:PYTHONDONTWRITEBYTECODE
    try {
        $env:PYTHONPATH = $backend
        $env:PYTHONDONTWRITEBYTECODE = '1'
        & $python -B -P -S -c $verification $root $transaction $CandidateVersion
        if ($LASTEXITCODE -ne 0) { throw 'The accepted software update owner or journal could not be verified.' }
    }
    finally {
        $env:PYTHONPATH = $priorPythonPath
        $env:PYTHONDONTWRITEBYTECODE = $priorBytecode
    }
}
$config = $nativeRoot + '\soai.exe.config'
if ([IO.File]::Exists($config)) {
    $actual = [Convert]::ToBase64String([IO.File]::ReadAllBytes($config))
    $candidate = [Convert]::ToBase64String([IO.File]::ReadAllBytes($CandidateConfigPath))
    if ($actual -cne $candidate) {
        $installedTemplate = $nativeRoot + '\installer-support\soai.exe.config'
        $installedManifest = $nativeRoot + '\installer-support\installed-files.txt'
        if (![IO.File]::Exists($installedTemplate) -or ![IO.File]::Exists($installedManifest) -or
            !([IO.File]::ReadAllLines($installedManifest) -contains 'soai.exe.config') -or
            $actual -cne [Convert]::ToBase64String([IO.File]::ReadAllBytes($installedTemplate))) {
            throw 'A custom launcher configuration conflicts with this installer. Existing configuration has been retained.'
        }
    }
}
if ($Mode -eq 'Target') {
    [IO.File]::WriteAllText($ClassificationPath, $classification, [Text.Encoding]::ASCII)
    [IO.File]::WriteAllText($ClassificationPath + '.target-root', $root, [Text.Encoding]::Unicode)
}
if ($Mode -eq 'Transactions') {
    $lockDirectory = $root + '\data\state\locks\soai.install.lock.d'
    if ([IO.Directory]::Exists((ConvertTo-InstallerFilesystemPath $lockDirectory))) {
        if ([string]::IsNullOrWhiteSpace($CandidateLauncherPath)) { throw 'The current control launcher is required to verify abandoned installation ownership.' }
        $priorConsoleEncoding = [Console]::OutputEncoding
        try {
            [Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
            & ([IO.Path]::GetFullPath($CandidateLauncherPath)) --recover-install-lock $lockDirectory | Out-Host
            if ($LASTEXITCODE -ne 0) { throw 'Installation ownership recovery failed. Its evidence has been retained for repair.' }
        } finally { [Console]::OutputEncoding = $priorConsoleEncoding }
    }
}
$currentProcess = Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$PID" -ErrorAction Stop
$installer = Get-Process -Id $currentProcess.ParentProcessId -ErrorAction Stop
try {
    $created = [double]$installer.StartTime.ToUniversalTime().ToFileTimeUtc() / 10000000.0 - 11644473600.0
    $milliseconds = [long][Math]::Floor($created * 1000.0)
    [IO.File]::WriteAllText($ClassificationPath + '.owner-start-ms', $milliseconds.ToString([Globalization.CultureInfo]::InvariantCulture), [Text.Encoding]::ASCII)
} finally { $installer.Dispose() }
