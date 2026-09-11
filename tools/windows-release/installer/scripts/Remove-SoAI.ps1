[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InstallRoot,
    [ValidateSet('Uninstall','ArchiveUninstall','Upgrade','Stop')][string]$Mode = 'Uninstall',
    [string]$ManifestPath = ''
)

$ErrorActionPreference = 'Stop'

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
    param([Parameter(Mandatory=$true)][string]$EntryName)
    return $EntryName.StartsWith('.soai_update_transaction_', [StringComparison]::OrdinalIgnoreCase) -or
        $EntryName.StartsWith('.soai_update_cleanup_', [StringComparison]::OrdinalIgnoreCase)
}

function Assert-SafeInstallRoot {
    param([Parameter(Mandatory=$true)][string]$Root)
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

    $marker = Join-Path $full '.soai-install-root'
    $looksLikeSoAI = (Test-Path -LiteralPath (Join-Path $full 'soai.exe')) -and
        (Test-Path -LiteralPath (Join-Path $full 'backend')) -and
        (Test-Path -LiteralPath (Join-Path $full 'frontend'))
    if ($Mode -in @('Uninstall', 'ArchiveUninstall') -and !(Test-Path -LiteralPath $marker)) {
        $rootChildren = @()
        if (Test-Path -LiteralPath $full -PathType Container) {
            $rootChildren = @(Get-ChildItem -LiteralPath $full -Force -ErrorAction Stop)
        }
        $isEmptyInstallRoot = $rootChildren.Count -eq 0
        $isOnlyStaleUninstaller = $rootChildren.Count -eq 1 -and
            [string]::Equals($rootChildren[0].Name, 'Uninstall.exe', [System.StringComparison]::OrdinalIgnoreCase) -and
            [string]::Equals((Split-Path -Leaf $full), 'SoAI', [System.StringComparison]::OrdinalIgnoreCase)
        if (!$isEmptyInstallRoot -and !$looksLikeSoAI -and !$isOnlyStaleUninstaller) {
            throw "SoAI install marker is missing. Refusing to uninstall from $full."
        }
    }
    if ($Mode -in @('Upgrade', 'Stop') -and !(Test-Path -LiteralPath $marker) -and !$looksLikeSoAI) {
        throw "The target does not look like a SoAI installation: $full"
    }
    if ($Mode -in @('Uninstall', 'ArchiveUninstall') -and (Test-Path -LiteralPath $full -PathType Container)) {
        foreach ($entry in Get-ChildItem -LiteralPath $full -Force -ErrorAction Stop) {
            if (Test-RetainedUpdateStorageName -EntryName $entry.Name) {
                throw 'A software update awaits recovery or cleanup. Reopen SoAI to complete it before uninstalling. No application files were removed.'
            }
        }
    }
    return $full
}

function Assert-SoAIStopped {
    param([Parameter(Mandatory=$true)][string]$Root)
    $runtimePython = Join-Path $Root 'soai_main_venv\Scripts\python.exe'
    $source = @'
import logging, os, sys
sys.path.insert(0, os.path.join(sys.argv[1], 'backend'))
from app.updater.soai_instance import is_instance_lock_held, resolve_instance_lock_path
from core.bootstrap.runtime_record_path import resolve_runtime_record_path
from core.runtime.instance_record import read_verified_runtime_instance_record
logger = logging.getLogger('installer.stop')
root = sys.argv[1]
record = read_verified_runtime_instance_record(resolve_runtime_record_path(root, logger=logger), base_dir=root)
if record is not None or is_instance_lock_held(logger=logger, lock_path=resolve_instance_lock_path(base_path=root)):
    raise RuntimeError('The installed application is still running or its instance lock cannot be verified.')
'@
    $arguments = '-c "' + $source + '" "' + $Root + '"'
    $probe = Start-Process -FilePath $runtimePython -ArgumentList $arguments -WorkingDirectory $Root -WindowStyle Hidden -PassThru -ErrorAction Stop
    if (!$probe) {
        throw 'The installed application shutdown could not be verified. No application files were removed.'
    }
    try {
        Wait-ForOwnedProcessExit -Process $probe -TimeoutMilliseconds 60000
        if ($probe.ExitCode -ne 0) {
            throw 'The installed application shutdown could not be verified. No application files were removed.'
        }
    }
    finally {
        $probe.Dispose()
    }
}

function Stop-SoAI {
    param([Parameter(Mandatory=$true)][string]$Root)
    $launcher = Join-Path $Root 'soai.exe'
    if (!(Test-Path -LiteralPath $launcher)) {
        return
    }
    Write-Step 'Stopping SoAI...'
    $process = Start-Process -FilePath $launcher -ArgumentList @('stop') -WorkingDirectory $Root -WindowStyle Hidden -PassThru -ErrorAction Stop
    if (!$process) {
        throw 'The installed SoAI stop command could not be started.'
    }
    try {
        Wait-ForOwnedProcessExit -Process $process -TimeoutMilliseconds 60000
        if ($process.ExitCode -ne 0) {
            Assert-SoAIStopped -Root $Root
        }
    }
    finally {
        $process.Dispose()
    }
    foreach ($candidate in [Diagnostics.Process]::GetProcessesByName('soai')) {
        try {
            if ($candidate.HasExited) {
                continue
            }
            $null = $candidate.Handle
            $executable = $candidate.MainModule.FileName
            if (![string]::Equals($executable, $launcher, [StringComparison]::OrdinalIgnoreCase)) {
                continue
            }
            $null = $candidate.CloseMainWindow()
            Wait-ForOwnedProcessExit -Process $candidate -TimeoutMilliseconds 10000
        }
        catch {
            if (!$candidate.HasExited) {
                throw
            }
        }
        finally {
            $candidate.Dispose()
        }
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

function Remove-FileIfPresent {
    param([Parameter(Mandatory=$true)][string]$Path)
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        Remove-Item -LiteralPath $Path -Force -ErrorAction Stop
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            throw "Failed to remove file: $Path"
        }
    }
}

function Remove-DirectoryTree {
    param([Parameter(Mandatory=$true)][string]$Path)
    if (!(Test-Path -LiteralPath $Path -PathType Container)) {
        return
    }
    try {
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
        return
    }
    catch {
    }

    $emptyRoot = Join-Path $env:TEMP ("SoAI-Empty-" + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $emptyRoot | Out-Null
    try {
        & "$env:WINDIR\System32\robocopy.exe" $emptyRoot $Path /MIR /XJ /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue
    }
    finally {
        Remove-Item -LiteralPath $emptyRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $Path -PathType Container) {
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
    if (!(Test-Path -LiteralPath $cachePath)) {
        return
    }
    $cacheDirectory = Get-Item -LiteralPath $cachePath -Force -ErrorAction Stop
    if (!$cacheDirectory.PSIsContainer -or
        ($cacheDirectory.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The Python bytecode cache is not a regular directory; source replacement was refused.'
    }
    $moduleName = [Regex]::Escape([IO.Path]::GetFileNameWithoutExtension($SourcePath))
    $cachePattern = '^' + $moduleName + '\.[^.]+(?:\.opt-[^.]+)?\.pyc$'
    foreach ($entry in Get-ChildItem -LiteralPath $cachePath -Force -ErrorAction Stop) {
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

function Remove-ManifestFiles {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [string]$ExplicitManifestPath = ''
    )
    $manifest = if ([string]::IsNullOrWhiteSpace($ExplicitManifestPath)) {
        Join-Path $Root 'installer-support\installed-files.txt'
    }
    else {
        Resolve-FullPath $ExplicitManifestPath
    }
    if (!(Test-Path -LiteralPath $manifest)) {
        if (![string]::IsNullOrWhiteSpace($ExplicitManifestPath)) {
            throw "The required SoAI cleanup manifest is missing: $manifest"
        }
        return
    }
    foreach ($line in Get-Content -LiteralPath $manifest) {
        $relative = ''
        if ($line -ne $null) {
            $relative = $line.Trim()
        }
        if ($relative.Length -eq 0) {
            continue
        }
        $target = Resolve-ChildPath -Root $Root -Child $relative
        if ($Mode -eq 'Upgrade' -and
            [string]::Equals($target, (Join-Path $Root 'soai.exe'), [StringComparison]::OrdinalIgnoreCase)) {
            continue
        }
        Remove-SourceBytecode -SourcePath $target
        Remove-FileIfPresent $target
    }
}

function Remove-Shortcuts {
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
    param([Parameter(Mandatory=$true)][string]$Root)
    if (!$Root.StartsWith('\\?\', [StringComparison]::Ordinal)) {
        if ($Root.StartsWith('\\', [StringComparison]::Ordinal)) {
            $Root = '\\?\UNC\' + $Root.Substring(2)
        }
        else {
            $Root = '\\?\' + $Root
        }
    }
    if (!(Test-Path -LiteralPath $Root -PathType Container)) {
        return
    }
    foreach ($directory in Get-ChildItem -LiteralPath $Root -Directory -Force -ErrorAction Stop) {
        if ((Test-RetainedUpdateStorageName -EntryName $directory.Name) -or
            ($directory.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            continue
        }
        Remove-EmptyDirectories -Root $directory.FullName
        if (!(Get-ChildItem -LiteralPath $directory.FullName -Force -ErrorAction Stop)) {
            Remove-Item -LiteralPath $directory.FullName -Force -ErrorAction Stop
        }
    }
}

function Remove-InstallRootIfEmpty {
    param([Parameter(Mandatory=$true)][string]$Root)
    if (!(Test-Path -LiteralPath $Root -PathType Container)) {
        return
    }

    $remaining = @(Get-ChildItem -LiteralPath $Root -Force -ErrorAction Stop)
    if ($remaining.Count -gt 0) {
        $names = ($remaining | Select-Object -First 8 -ExpandProperty Name) -join ', '
        if ($remaining.Count -gt 8) {
            $names = "$names, ..."
        }
        throw "SoAI cleanup left files in ${Root}: $names"
    }

    Remove-Item -LiteralPath $Root -Force -ErrorAction Stop
    if (Test-Path -LiteralPath $Root -PathType Container) {
        throw "Failed to remove empty SoAI install directory: $Root"
    }
}

$root = Assert-SafeInstallRoot $InstallRoot
Stop-SoAI -Root $root

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

Write-Step 'Removing SoAI files and app data...'
if ($Mode -eq 'Uninstall') {
    Remove-Shortcuts
}
Remove-ManifestFiles -Root $root -ExplicitManifestPath $ManifestPath
foreach ($relative in @(
    'backend',
    'frontend',
    'plugins',
    'licenses',
    'data',
    'python',
    'python-3.13',
    'runtime',
    'soai_main_venv',
    'soai_python',
    'webview2',
    'installer-support'
)) {
    Remove-DirectoryIfPresent (Resolve-ChildPath -Root $root -Child $relative)
}

foreach ($relative in @(
    '.soai-install-root',
    '.soai_install_manifest.json',
    '.soai_install_in_progress',
    'soai.exe',
    'Uninstall.exe',
    'soai-app.ico',
    'install-soai-from-release.bat',
    'requirements.txt',
    'README.md',
    'LICENSE.md',
    'LICENSING.md',
    'ORGANIZATION-EVALUATION-TERMS.md',
    'PERSONAL-PURCHASE-TERMS.md',
    'NOTICE',
    'DOCUMENTATION.md',
    'COMMERCIAL-LICENSING-AVAILABILITY.md',
    'COMMERCIAL-LICENSE.md',
    'COMMERCIAL-SUPPORT-TERMS.md',
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
)) {
    Remove-FileIfPresent (Resolve-ChildPath -Root $root -Child $relative)
}

Remove-EmptyDirectories -Root $root
Remove-InstallRootIfEmpty -Root $root

Write-Step 'SoAI uninstall cleanup completed.'
