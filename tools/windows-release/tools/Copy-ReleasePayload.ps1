[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$PayloadDir,
    [Parameter(Mandatory=$true)][string]$LauncherBuildDir,
    [Parameter(Mandatory=$true)][string]$WindowsReleaseRoot,
    [Parameter(Mandatory=$true)][string]$Version
)

$ErrorActionPreference = 'Stop'

function Resolve-FullPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $executionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
}

function Assert-SafeGeneratedDirectory {
    param([Parameter(Mandatory=$true)][string]$Path)
    $full = Resolve-FullPath $Path
    $root = [System.IO.Path]::GetPathRoot($full)
    if ([string]::Equals($full.TrimEnd('\'), $root.TrimEnd('\'), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clear a drive root: $full"
    }
    if ($full.Length -lt 12) {
        throw "Refusing to clear an unexpectedly short path: $full"
    }
    return $full
}

function Get-RelativePath {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$Path
    )
    $prefix = $Root.TrimEnd('\') + '\'
    if (!$Path.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        return ''
    }
    return $Path.Substring($prefix.Length)
}

function Test-ExcludedDirectory {
    param([string]$RelativePath)
    if ([string]::IsNullOrWhiteSpace($RelativePath)) {
        return $false
    }
    $normalized = $RelativePath.Trim('\').ToLowerInvariant()
    $parts = $normalized -split '\\'
    foreach ($part in $parts) {
        if ($script:ExcludedAnyDirectoryNames.Contains($part)) {
            return $true
        }
    }
    if ($parts.Count -eq 1 -and $script:ExcludedRootDirectoryNames.Contains($normalized)) {
        return $true
    }
    foreach ($excluded in $script:ExcludedRelativeDirectories) {
        if ($normalized -eq $excluded -or $normalized.StartsWith($excluded + '\')) {
            return $true
        }
    }
    return $false
}

function Test-ExcludedFile {
    param(
        [string]$RelativePath,
        [string]$Name
    )
    $normalized = $RelativePath.Trim('\').ToLowerInvariant()
    if ($script:ExcludedRootFiles.Contains($normalized)) {
        return $true
    }
    foreach ($pattern in $script:ExcludedFilePatterns) {
        if ($Name -like $pattern) {
            return $true
        }
    }
    return $false
}

function Copy-FilteredTree {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination
    )
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    foreach ($item in Get-ChildItem -LiteralPath $Source -Force) {
        $relative = Get-RelativePath -Root $script:ResolvedSourceRoot -Path $item.FullName
        if ($item.PSIsContainer) {
            if (Test-ExcludedDirectory $relative) {
                continue
            }
            Copy-FilteredTree -Source $item.FullName -Destination (Join-Path $Destination $item.Name)
            continue
        }

        if (Test-ExcludedDirectory ([System.IO.Path]::GetDirectoryName($relative))) {
            continue
        }
        if (Test-ExcludedFile -RelativePath $relative -Name $item.Name) {
            continue
        }
        Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $Destination $item.Name) -Force
    }
}

function Assert-FilteredPayload {
    param([Parameter(Mandatory=$true)][string]$PayloadRoot)
    foreach ($item in Get-ChildItem -LiteralPath $PayloadRoot -Recurse -Force) {
        $relative = Get-RelativePath -Root $PayloadRoot -Path $item.FullName
        if ($item.PSIsContainer) {
            if (Test-ExcludedDirectory $relative) {
                throw "Windows payload contains a forbidden directory: $relative"
            }
            continue
        }
        if ((Test-ExcludedDirectory ([System.IO.Path]::GetDirectoryName($relative))) `
            -or (Test-ExcludedFile -RelativePath $relative -Name $item.Name)) {
            throw "Windows payload contains a generated or sensitive file: $relative"
        }
    }
}

$script:ResolvedSourceRoot = Resolve-FullPath $SourceRoot
$payloadRoot = Assert-SafeGeneratedDirectory $PayloadDir
$launcherRoot = Resolve-FullPath $LauncherBuildDir
$releaseKitRoot = Resolve-FullPath $WindowsReleaseRoot

$script:ExcludedAnyDirectoryNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(
    '.git',
    '.github',
    '.hg',
    '.svn',
    '.cache',
    '.coverage',
    '.idea',
    '.vscode',
    '.mypy_cache',
    '.nox',
    '.nyc_output',
    '.pytest_cache',
    '.ruff_cache',
    '.tmp',
    '.tox',
    '.vite',
    '__pycache__',
    'coverage',
    'dist',
    'htmlcov',
    'node_modules',
    'out',
    'output',
    'playwright-output',
    'playwright-report',
    'screenshots',
    'test-logs',
    'test-results',
    'test-work',
    'tmp',
    '.soai-release-signing-gnupg',
    'openpgp-revocs.d',
    'private-keys-v1.d'
) | ForEach-Object { [void]$script:ExcludedAnyDirectoryNames.Add($_) }

$script:ExcludedRootDirectoryNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(
    '.windows-build',
    'python',
    'python-3.13',
    'runtime',
    'soai_main_venv',
    'soai_python',
    'webview2',
    'windows_release'
) | ForEach-Object { [void]$script:ExcludedRootDirectoryNames.Add($_) }

$script:ExcludedRelativeDirectories = @(
    'data\backups',
    'data\backends',
    'data\cache',
    'data\chroma_rag',
    'data\database',
    'data\files',
    'data\gpu',
    'data\locks',
    'data\logs',
    'data\state',
    'data\temp',
    'data\user_files'
)

$script:ExcludedRootFiles = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(
    'create-soai-windows-installer.cmd',
    'create-soai-windows-installer.ps1',
    'soai.exe',
    'soai.sh',
    'soai.command',
    'install-soai-from-release.sh',
    'install-soai-from-release.command',
    'microsoft.web.webview2.core.dll',
    'microsoft.web.webview2.winforms.dll',
    'webview2loader.dll',
    'windows-build-kit.txt',
    'data\secret.key'
) | ForEach-Object { [void]$script:ExcludedRootFiles.Add($_) }

$script:ExcludedFilePatterns = @(
    '.coverage',
    '.coverage.*',
    '.ds_store',
    '.env',
    '.env.*',
    '.eslintcache',
    'coverage-final.json',
    'coverage.xml',
    'desktop.ini',
    'lcov.info',
    'thumbs.db',
    '*-this-session-is-being-continued-from-a-previous-c.txt',
    'scratchpad_*.png',
    'verify_sb*.mjs',
    '*.cer',
    '*.crt',
    '*.dmp',
    '*.dump',
    '*.exe',
    '*.gpg',
    '*.har',
    '*.jks',
    '*.kbx',
    '*.key',
    '*.keystore',
    '*.map',
    '*.nupkg',
    '*.orig',
    '*.p12',
    '*.pcap',
    '*.pem',
    '*.pfx',
    '*.prof',
    '*.pyc',
    '*.pyo',
    '*.rej',
    '*.sqlite',
    '*.sqlite3',
    '*.status',
    '*.swo',
    '*.swp',
    '*.temp',
    '*.trace',
    '*.zip',
    '*.log',
    '*.tmp',
    '*.bak',
    '*.db',
    '*.soaiplugin.yaml',
    '*.soaiplugin.yml',
    'soai.exe.backup-*'
)

if (Test-Path -LiteralPath $payloadRoot) {
    Remove-Item -LiteralPath $payloadRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $payloadRoot | Out-Null

Copy-FilteredTree -Source $script:ResolvedSourceRoot -Destination $payloadRoot
Assert-FilteredPayload -PayloadRoot $payloadRoot

$runtimeAssetsSource = Join-Path $script:ResolvedSourceRoot 'runtime-assets'
$runtimeAssetsDestination = Join-Path $payloadRoot 'runtime-assets'
$expectedRuntimeAssets = @(
    'tesseract-5.5.3-windows-x64.zip',
    'tesseract-5.5.3-windows-x64.json'
)
New-Item -ItemType Directory -Force -Path $runtimeAssetsDestination | Out-Null
foreach ($file in $expectedRuntimeAssets) {
    $source = Join-Path $runtimeAssetsSource $file
    if (!(Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Windows build kit lacks managed runtime asset: $source"
    }
    Copy-Item -LiteralPath $source -Destination $runtimeAssetsDestination -Force
}
$unexpectedRuntimeAssets = @(Get-ChildItem -LiteralPath $runtimeAssetsDestination -File -Force |
    Where-Object { $_.Name -notin $expectedRuntimeAssets })
if ($unexpectedRuntimeAssets.Count -ne 0) {
    throw 'Windows payload contains an unexpected managed runtime asset.'
}

$packagedPluginConfigurations = Get-ChildItem -LiteralPath $payloadRoot -Recurse -File -Force |
    Where-Object { $_.Name -like '*.soaiplugin.yaml' -or $_.Name -like '*.soaiplugin.yml' }
if ($packagedPluginConfigurations) {
    throw 'Windows payload contains runtime-generated plugin configuration.'
}

$editionReleaseInfo = [ordered]@{
    artifact_type = 'complete'
    core_version = $Version
    edition = 'soai-core'
    product = 'SoAI'
    schema_version = 1
    version = $Version
} | ConvertTo-Json -Depth 3
Set-Content -LiteralPath (Join-Path $payloadRoot 'release-info-v1.json') `
    -Value $editionReleaseInfo `
    -Encoding UTF8

foreach ($file in @('soai.exe', 'soai-app.ico', 'Microsoft.Web.WebView2.Core.dll', 'Microsoft.Web.WebView2.WinForms.dll', 'WebView2Loader.dll')) {
    $source = Join-Path $launcherRoot $file
    if (!(Test-Path -LiteralPath $source)) {
        throw "Launcher build output is missing: $source"
    }
    Copy-Item -LiteralPath $source -Destination $payloadRoot -Force
}

$supportDir = Join-Path $payloadRoot 'installer-support'
New-Item -ItemType Directory -Force -Path $supportDir | Out-Null
Copy-Item -LiteralPath (Join-Path $releaseKitRoot 'installer\scripts\Install-SoAIRuntime.ps1') -Destination $supportDir -Force
Copy-Item -LiteralPath (Join-Path $releaseKitRoot 'installer\scripts\Remove-SoAI.ps1') -Destination $supportDir -Force

$releaseInfo = @{
    product = 'SoAI'
    version = $Version
} | ConvertTo-Json -Depth 3
Set-Content -LiteralPath (Join-Path $supportDir 'release-info.json') -Value $releaseInfo -Encoding UTF8

$manifestPath = Join-Path $supportDir 'installed-files.txt'
$files = Get-ChildItem -LiteralPath $payloadRoot -Recurse -File -Force |
    Sort-Object FullName |
    ForEach-Object { Get-RelativePath -Root $payloadRoot -Path $_.FullName }
Set-Content -LiteralPath $manifestPath -Value $files -Encoding ASCII

Write-Host "Payload staged at: $payloadRoot"
