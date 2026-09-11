[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InstallRoot,
    [string]$BackupRoot,
    [string]$CandidateManifestPath,
    [Parameter(Mandatory=$true)][ValidateSet('Backup','Restore','Cleanup','Inventory')][string]$Mode
)

$ErrorActionPreference = 'Stop'

function Resolve-FullPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $executionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
}

function ConvertTo-ExtendedPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $resolved = Resolve-FullPath $Path
    if ($resolved.StartsWith('\\?\', [StringComparison]::Ordinal)) {
        return $resolved
    }
    if ($resolved.StartsWith('\\', [StringComparison]::Ordinal)) {
        return '\\?\UNC\' + $resolved.Substring(2)
    }
    return '\\?\' + $resolved
}

function Resolve-ChildPath {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$Child
    )
    $resolvedRoot = Resolve-FullPath $Root
    $resolvedChild = Resolve-FullPath (Join-Path $resolvedRoot $Child)
    $prefix = $resolvedRoot.TrimEnd('\') + '\'
    if (!$resolvedChild.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to use a path outside its transaction root: $resolvedChild"
    }
    return $resolvedChild
}

function Assert-SafeRoots {
    $resolvedInstallRoot = Resolve-FullPath $InstallRoot
    $resolvedBackupRoot = Resolve-FullPath $BackupRoot
    $driveRoot = [System.IO.Path]::GetPathRoot($resolvedInstallRoot).TrimEnd('\')
    if ([string]::Equals($resolvedInstallRoot.TrimEnd('\'), $driveRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'The SoAI install root cannot be a drive root.'
    }
    if ([string]::Equals($resolvedInstallRoot.TrimEnd('\'), $resolvedBackupRoot.TrimEnd('\'), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'The SoAI upgrade backup must be separate from the install root.'
    }
    if (!(Split-Path -Leaf $resolvedBackupRoot).Contains('-SoAI-Upgrade-')) {
        throw 'The SoAI upgrade backup directory name is invalid.'
    }
    return @($resolvedInstallRoot, $resolvedBackupRoot)
}

function Copy-ManifestFiles {
    param(
        [Parameter(Mandatory=$true)][string]$SourceRoot,
        [Parameter(Mandatory=$true)][string]$DestinationRoot,
        [Parameter(Mandatory=$true)][string]$ManifestPath
    )
    foreach ($line in Get-Content -LiteralPath $ManifestPath) {
        $relative = $line.Trim()
        if ($relative.Length -eq 0) {
            continue
        }
        $source = ConvertTo-ExtendedPath (Resolve-ChildPath -Root $SourceRoot -Child $relative)
        if (!(Test-Path -LiteralPath $source -PathType Leaf)) {
            continue
        }
        $destination = ConvertTo-ExtendedPath (Resolve-ChildPath -Root $DestinationRoot -Child $relative)
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }
}

function Copy-RollbackPath {
    param(
        [Parameter(Mandatory=$true)][string]$SourceRoot,
        [Parameter(Mandatory=$true)][string]$DestinationRoot,
        [Parameter(Mandatory=$true)][string]$RelativePath
    )
    $source = ConvertTo-ExtendedPath (Resolve-ChildPath -Root $SourceRoot -Child $RelativePath)
    if (!(Test-Path -LiteralPath $source)) {
        return
    }
    $destination = ConvertTo-ExtendedPath (Resolve-ChildPath -Root $DestinationRoot -Child $RelativePath)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
}

function Remove-RollbackPath {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$RelativePath
    )
    $target = ConvertTo-ExtendedPath (Resolve-ChildPath -Root $Root -Child $RelativePath)
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

function Restore-Launcher {
    param(
        [Parameter(Mandatory=$true)][string]$SourceRoot,
        [Parameter(Mandatory=$true)][string]$DestinationRoot
    )
    $source = Resolve-ChildPath -Root $SourceRoot -Child 'soai.exe'
    if (!(Test-Path -LiteralPath $source -PathType Leaf)) {
        return
    }
    $destination = Resolve-ChildPath -Root $DestinationRoot -Child 'soai.exe'
    $candidate = Resolve-ChildPath -Root $DestinationRoot -Child 'installer-support\.soai-launcher.pending'
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $candidate) | Out-Null
    if (Test-Path -LiteralPath $candidate) {
        Remove-Item -LiteralPath $candidate -Force
    }
    Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
public static class SoAIInstallerLauncherFile {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern bool MoveFileEx(string source, string destination, int flags);
}
'@
    $original = [IO.File]::OpenRead($source)
    try {
        $staged = [IO.File]::Open($candidate, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try {
            $original.CopyTo($staged)
            $staged.Flush($true)
        }
        finally { $staged.Dispose() }
    }
    finally { $original.Dispose() }
    if (![SoAIInstallerLauncherFile]::MoveFileEx($candidate, $destination, 9)) {
        throw [ComponentModel.Win32Exception]::new(
            [Runtime.InteropServices.Marshal]::GetLastWin32Error(),
            'The retained SoAI launcher could not be restored atomically.'
        )
    }
}

$runtimeRollbackDirectories = @(
    'python',
    'python-3.13',
    'runtime',
    'soai_main_venv',
    'soai_python',
    'webview2',
    'data\state\java',
    'data\state\playwright-browsers',
    'data\state\tika',
    'data\state\tiktoken-cache',
    'installer-support\logs'
)
$runtimeRollbackFiles = @(
    'data\state\windows-install.json',
    'msvcp140.dll',
    'msvcp140_1.dll',
    'msvcp140_2.dll',
    'msvcp140_atomic_wait.dll',
    'msvcp140_codecvt_ids.dll',
    'vcruntime140.dll',
    'vcruntime140_1.dll'
)


$installationMetadataPaths = @(
    '.soai-install-root',
    'Uninstall.exe',
    'installer-support\installed-files.txt'
)
$runtimeRollbackPaths = @($runtimeRollbackDirectories) + @($runtimeRollbackFiles)
if ($Mode -eq 'Inventory') {
    $manifestPath = Join-Path $InstallRoot 'installer-support\installed-files.txt'
    if (!(Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw 'The existing SoAI installation manifest is missing.'
    }
    $manifestFiles = @(Get-Content -LiteralPath $manifestPath | ForEach-Object { $_.Trim() } | Where-Object { $_.Length -gt 0 })
    [ordered]@{
        directories = @($runtimeRollbackDirectories | ForEach-Object { $_.Replace('\', '/') })
        files = @((@($runtimeRollbackFiles) + @($installationMetadataPaths) + $manifestFiles) | ForEach-Object { $_.Replace('\', '/') } | Sort-Object -Unique)
    } | ConvertTo-Json -Compress
    exit 0
}
if ([string]::IsNullOrWhiteSpace($BackupRoot)) {
    throw 'The SoAI upgrade transaction requires a backup root.'
}
$roots = Assert-SafeRoots
$resolvedInstallRoot = $roots[0]
$resolvedBackupRoot = $roots[1]
$backupMarker = Join-Path $resolvedBackupRoot '.soai-upgrade-backup'
$backupMarkerValue = 'SoAI upgrade backup V1'

if ($Mode -eq 'Backup') {
    if (Test-Path -LiteralPath $resolvedBackupRoot) {
        if (Get-ChildItem -LiteralPath $resolvedBackupRoot -Force | Select-Object -First 1) {
            throw 'The SoAI upgrade backup directory is not empty.'
        }
    }
    else {
        New-Item -ItemType Directory -Path $resolvedBackupRoot | Out-Null
    }
    try {
        $manifestPath = Join-Path $resolvedInstallRoot 'installer-support\installed-files.txt'
        if (!(Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
            throw 'The existing SoAI installation manifest is missing.'
        }
        Copy-ManifestFiles -SourceRoot $resolvedInstallRoot -DestinationRoot $resolvedBackupRoot -ManifestPath $manifestPath
        foreach ($relative in $runtimeRollbackPaths) {
            Copy-RollbackPath -SourceRoot $resolvedInstallRoot -DestinationRoot $resolvedBackupRoot -RelativePath $relative
        }
        foreach ($relative in $installationMetadataPaths) {
            $source = Resolve-ChildPath -Root $resolvedInstallRoot -Child $relative
            if (Test-Path -LiteralPath $source -PathType Leaf) {
                $destination = Resolve-ChildPath -Root $resolvedBackupRoot -Child $relative
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
                Copy-Item -LiteralPath $source -Destination $destination -Force
            }
        }
        Set-Content -LiteralPath $backupMarker -Value $backupMarkerValue -Encoding ASCII
    }
    catch {
        $backupError = $_
        try {
            Remove-Item -LiteralPath (ConvertTo-ExtendedPath $resolvedBackupRoot) -Recurse -Force -ErrorAction Stop
        }
        catch {
            Write-Warning 'Failed to remove the incomplete SoAI upgrade backup.'
        }
        throw $backupError
    }
    exit 0
}

if (!(Test-Path -LiteralPath $backupMarker -PathType Leaf)) {
    throw 'The SoAI upgrade backup marker is missing.'
}

if ([IO.File]::ReadAllText($backupMarker).TrimEnd([char[]]"`r`n") -cne $backupMarkerValue) {
    throw 'The SoAI upgrade backup marker is invalid; preserve the backup for repair.'
}

if ($Mode -eq 'Restore') {
    $backupManifest = Resolve-ChildPath -Root $resolvedBackupRoot -Child 'installer-support\installed-files.txt'
    if (!(Test-Path -LiteralPath $backupManifest -PathType Leaf)) {
        throw 'The retained SoAI installation manifest is missing; no restoration was attempted.'
    }
    foreach ($line in Get-Content -LiteralPath $backupManifest) {
        $relative = $line.Trim()
        if ($relative.Length -gt 0) {
            Resolve-ChildPath -Root $resolvedBackupRoot -Child $relative | Out-Null
        }
    }
    if (![string]::IsNullOrWhiteSpace($CandidateManifestPath)) {
        & (Join-Path $PSScriptRoot 'Remove-SoAI.ps1') -InstallRoot $resolvedInstallRoot -Mode Upgrade -ManifestPath $CandidateManifestPath
        if (!$?) {
            throw 'The candidate files could not be removed; retained originals were not copied.'
        }
    }
    foreach ($relative in $runtimeRollbackPaths) {
        Remove-RollbackPath -Root $resolvedInstallRoot -RelativePath $relative
    }
    foreach ($item in Get-ChildItem -LiteralPath $resolvedBackupRoot -Force) {
        if ($item.Name -eq '.soai-upgrade-backup' -or $item.Name -eq 'soai.exe') {
            continue
        }
        Copy-Item -LiteralPath (ConvertTo-ExtendedPath $item.FullName) -Destination (ConvertTo-ExtendedPath $resolvedInstallRoot) -Recurse -Force
    }
    Restore-Launcher -SourceRoot $resolvedBackupRoot -DestinationRoot $resolvedInstallRoot
    exit 0
}

Remove-Item -LiteralPath (ConvertTo-ExtendedPath $resolvedBackupRoot) -Recurse -Force
