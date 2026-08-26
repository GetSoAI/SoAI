[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InstallRoot,
    [ValidateSet('Uninstall','Upgrade')][string]$Mode = 'Uninstall'
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
    if ($Mode -eq 'Uninstall' -and !(Test-Path -LiteralPath $marker)) {
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
    if ($Mode -eq 'Upgrade' -and !(Test-Path -LiteralPath $marker) -and !$looksLikeSoAI) {
        throw "The target does not look like a SoAI installation: $full"
    }
    return $full
}

function Stop-SoAI {
    param([Parameter(Mandatory=$true)][string]$Root)
    $launcher = Join-Path $Root 'soai.exe'
    if (!(Test-Path -LiteralPath $launcher)) {
        return
    }
    Write-Step 'Stopping SoAI...'
    $process = Start-Process -FilePath $launcher -ArgumentList @('stop') -WorkingDirectory $Root -WindowStyle Hidden -PassThru -ErrorAction SilentlyContinue
    if (!$process) {
        return
    }
    if (!$process.WaitForExit(60000)) {
        try {
            $process.Kill()
        }
        catch {
        }
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

function Remove-ManifestFiles {
    param([Parameter(Mandatory=$true)][string]$Root)
    $manifest = Join-Path $Root 'installer-support\installed-files.txt'
    if (!(Test-Path -LiteralPath $manifest)) {
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
    if (!(Test-Path -LiteralPath $Root -PathType Container)) {
        return
    }
    Get-ChildItem -LiteralPath $Root -Recurse -Directory -Force |
        Sort-Object FullName -Descending |
        ForEach-Object {
            try {
                if (!(Get-ChildItem -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue)) {
                    Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
                }
            }
            catch {
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
Remove-Shortcuts

if ($Mode -eq 'Upgrade') {
    Write-Step 'Removing files from the previous SoAI install manifest...'
    Remove-ManifestFiles -Root $root
    Remove-DirectoryIfPresent (Join-Path $root 'webview2')
    Remove-EmptyDirectories -Root $root
    return
}

Write-Step 'Removing SoAI files and app data...'
Remove-ManifestFiles -Root $root
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
