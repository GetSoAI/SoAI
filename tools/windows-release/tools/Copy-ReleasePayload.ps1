[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$PayloadDir,
    [Parameter(Mandatory=$true)][string]$LauncherBuildDir,
    [Parameter(Mandatory=$true)][string]$WindowsReleaseRoot,
    [Parameter(Mandatory=$true)][string]$Version
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

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
        if ($script:ExcludedAnyDirectoryNames.Contains($part) -or $part -like '*_check') {
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
    param(
        [Parameter(Mandatory=$true)][string]$PayloadRoot,
        [switch]$PermitBuiltPayloadFiles
    )
    foreach ($item in Get-ChildItem -LiteralPath $PayloadRoot -Recurse -Force) {
        $relative = Get-RelativePath -Root $PayloadRoot -Path $item.FullName
        if ($item.PSIsContainer) {
            if (Test-ExcludedDirectory $relative) {
                throw "Windows payload contains a forbidden directory: $relative"
            }
            continue
        }
        $excludedFile = Test-ExcludedFile -RelativePath $relative -Name $item.Name
        $builtPayloadFile = $PermitBuiltPayloadFiles -and $script:BuiltPayloadFiles.Contains($relative)
        if ((Test-ExcludedDirectory ([System.IO.Path]::GetDirectoryName($relative))) `
            -or ($excludedFile -and !$builtPayloadFile)) {
            throw "Windows payload contains a generated or sensitive file: $relative"
        }
    }
}

function Assert-WindowsLicenseInventory {
    param([Parameter(Mandatory=$true)][string]$PayloadRoot)
    $licensesRoot = Join-Path $PayloadRoot 'licenses'
    if (!(Test-Path -LiteralPath $licensesRoot -PathType Container)) {
        throw 'Windows payload lacks its licenses directory.'
    }
    $expected = @(
        'Apache-2.0.txt',
        'FRONTEND-THIRD-PARTY-LICENSES.txt',
        'MIT.txt',
        'MSVC-RUNTIME-NOTICE.txt',
        'Microsoft-OpenJDK-NOTICE.txt',
        'NSIS-LICENSE.txt',
        'OFL.txt',
        'OpenJDK-ADDITIONAL-LICENSE-INFO.txt',
        'OpenJDK-GPLv2.txt',
        'OpenSSL-NOTICE.txt',
        'PLAYWRIGHT-CHROMIUM-NOTICES.txt',
        'PYTHON-THIRD-PARTY-NOTICES.txt',
        'Python-3.13-LICENSE.txt',
        'SBOM-PYTHON-CYCLONEDX.json',
        'TESSERACT-WINDOWS-RUNTIME-NOTICES.txt',
        'THIRD_PARTY_BACKEND_LICENSES.md',
        'THIRD_PARTY_LOGO_NOTICES.md',
        'WINDOWS-THIRD-PARTY-NOTICES.txt',
        'legal_document_catalog.json',
        'libffi-NOTICE.txt',
        'webview2'
    ) | Sort-Object
    $licenseEntries = @(Get-ChildItem -LiteralPath $licensesRoot -Force)
    $actual = @($licenseEntries | Select-Object -ExpandProperty Name | Sort-Object)
    if ((Compare-Object -ReferenceObject $expected -DifferenceObject $actual).Count -ne 0) {
        throw 'Windows payload license inventory does not match the platform contract.'
    }
    $invalidLicenseEntries = @(
        $licenseEntries | Where-Object {
            ($_.Name -eq 'webview2' -and !$_.PSIsContainer) -or
            ($_.Name -ne 'webview2' -and $_.PSIsContainer)
        }
    )
    if ($invalidLicenseEntries.Count -ne 0) {
        throw 'Windows payload license material has an invalid file type.'
    }
    $webViewLicensesRoot = Join-Path $licensesRoot 'webview2'
    if (!(Test-Path -LiteralPath $webViewLicensesRoot -PathType Container)) {
        throw 'Windows payload WebView2 license directory is invalid.'
    }
    $expectedWebViewLicenses = @(
        'Microsoft.Web.WebView2.SDK-LICENSE.txt',
        'Microsoft.Web.WebView2.SDK-NOTICE.txt',
        'README.txt'
    ) | Sort-Object
    $webViewLicenseEntries = @(Get-ChildItem -LiteralPath $webViewLicensesRoot -Force)
    $actualWebViewLicenses = @($webViewLicenseEntries | Select-Object -ExpandProperty Name | Sort-Object)
    if ((Compare-Object -ReferenceObject $expectedWebViewLicenses -DifferenceObject $actualWebViewLicenses).Count -ne 0 `
        -or @($webViewLicenseEntries | Where-Object { $_.PSIsContainer }).Count -ne 0) {
        throw 'Windows payload WebView2 license inventory does not match the platform contract.'
    }
}

function Assert-WindowsPlatformPayload {
    param([Parameter(Mandatory=$true)][string]$PayloadRoot)
    $posixLauncher = Join-Path $PayloadRoot 'backend\core\bootstrap\launcher_posix'
    if (Test-Path -LiteralPath $posixLauncher) {
        throw 'Windows payload contains POSIX launcher material.'
    }
    $foreignFiles = @(
        Get-ChildItem -LiteralPath $PayloadRoot -Recurse -File -Force |
            Where-Object { $_.Extension -in @('.sh', '.command') }
    )
    if ($foreignFiles.Count -ne 0) {
        throw 'Windows payload contains foreign-platform executable material.'
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
    '__snapshots__',
    'fixtures',
    'mockplugins',
    'mocks',
    'test',
    'tests',
    'unit',
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
    'backend\core\bootstrap\launcher_posix',
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

$script:BuiltLauncherRootFiles = @(
    'soai.exe',
    'soai-app.ico',
    'Microsoft.Web.WebView2.Core.dll',
    'Microsoft.Web.WebView2.WinForms.dll',
    'WebView2Loader.dll'
)

$script:ManagedRuntimeAssetFiles = @(
    'tesseract-5.5.3-windows-x64.zip',
    'tesseract-5.5.3-windows-x64.json'
)

$script:BuiltPayloadFiles = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(
    $script:BuiltLauncherRootFiles
    $script:ManagedRuntimeAssetFiles | ForEach-Object { "runtime-assets\$_" }
) | ForEach-Object { [void]$script:BuiltPayloadFiles.Add($_) }

$script:ExcludedFilePatterns = @(
    '.gitignore',
    '.bandit',
    '.depcheckrc',
    '.editorconfig',
    '.prettier*',
    'prettier.config.*',
    '.pylintrc',
    '.coveragerc',
    '.eslintrc*',
    '.stylelintrc*',
    'eslint.config.*',
    'stylelint.config.*',
    'conftest.py',
    'mypy.ini',
    'pyrightconfig.json',
    'pytest.ini',
    'requirements-dev.txt',
    'ruff.toml',
    '.ruff.toml',
    'tox.ini',
    'playwright.config.*',
    'playwright-test.d.ts',
    'vitest.config.*',
    'tsconfig.playwright.json',
    'test_*',
    'test-*',
    '*.test.*',
    '*.spec.*',
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
Assert-WindowsPlatformPayload -PayloadRoot $payloadRoot
Assert-WindowsLicenseInventory -PayloadRoot $payloadRoot

$runtimeAssetsSource = Join-Path $script:ResolvedSourceRoot 'runtime-assets'
$runtimeAssetsDestination = Join-Path $payloadRoot 'runtime-assets'
$expectedRuntimeAssets = $script:ManagedRuntimeAssetFiles
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

$editionReleaseInfo = ([ordered]@{
    artifact_type = 'complete'
    core_version = $Version
    edition = 'soai-core'
    product = 'SoAI'
    schema_version = 1
    version = $Version
} | ConvertTo-Json -Depth 3) + "`n"
[IO.File]::WriteAllText(
    (Join-Path $payloadRoot 'release-info-v1.json'),
    $editionReleaseInfo,
    [Text.UTF8Encoding]::new($false)
)

foreach ($file in $script:BuiltLauncherRootFiles) {
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
Copy-Item -LiteralPath (Join-Path $releaseKitRoot 'installer\scripts\Preserve-SoAIUpgrade.ps1') -Destination $supportDir -Force

$releaseInfo = (@{
    product = 'SoAI'
    version = $Version
} | ConvertTo-Json -Depth 3) + "`n"
[IO.File]::WriteAllText(
    (Join-Path $supportDir 'release-info.json'),
    $releaseInfo,
    [Text.UTF8Encoding]::new($false)
)

$manifestPath = Join-Path $supportDir 'installed-files.txt'
$files = Get-ChildItem -LiteralPath $payloadRoot -Recurse -File -Force |
    Sort-Object FullName |
    ForEach-Object { Get-RelativePath -Root $payloadRoot -Path $_.FullName }
Set-Content -LiteralPath $manifestPath -Value $files -Encoding ASCII

Assert-FilteredPayload -PayloadRoot $payloadRoot -PermitBuiltPayloadFiles
Assert-WindowsPlatformPayload -PayloadRoot $payloadRoot
Assert-WindowsLicenseInventory -PayloadRoot $payloadRoot

Write-Host "Payload staged at: $payloadRoot"
