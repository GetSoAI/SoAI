[CmdletBinding()]
param(
    [string]$SourceRoot,
    [string]$OutputDir,
    [string]$MakensisPath,
    [switch]$NoNSISBootstrap,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    $SourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

function Resolve-FullPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $executionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
}

function Assert-FilesMatch {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Staged,
        [Parameter(Mandatory=$true)][string]$FailureMessage
    )
    if (!(Test-Path -LiteralPath $Staged)) {
        throw $FailureMessage
    }
    $sourceHash = (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash
    $stagedHash = (Get-FileHash -LiteralPath $Staged -Algorithm SHA256).Hash
    if ($sourceHash -ne $stagedHash) {
        throw $FailureMessage
    }
}

function Assert-PreparedWindowsSource {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$ExpectedVersion
    )
    $releaseInfoPath = Join-Path $Root 'release-info-v1.json'
    if (!(Test-Path -LiteralPath $releaseInfoPath -PathType Leaf)) {
        throw 'Prepared Windows source lacks release-info-v1.json.'
    }
    $releaseInfo = Get-Content -LiteralPath $releaseInfoPath -Raw | ConvertFrom-Json
    $releaseInfoFields = @($releaseInfo.PSObject.Properties.Name | Sort-Object)
    $expectedReleaseInfoFields = @(
        'artifact_type',
        'core_version',
        'edition',
        'product',
        'schema_version',
        'version'
    )
    if ((Compare-Object $releaseInfoFields $expectedReleaseInfoFields).Count -ne 0 `
        -or $releaseInfo.schema_version -ne 1 `
        -or $releaseInfo.product -ne 'SoAI' `
        -or $releaseInfo.edition -ne 'soai-core' `
        -or $releaseInfo.artifact_type -ne 'windows' `
        -or $releaseInfo.version -ne $ExpectedVersion `
        -or $releaseInfo.core_version -ne $ExpectedVersion) {
        throw 'Prepared Windows source release identity is invalid.'
    }
    foreach ($relativePath in @(
        'backend\main.py',
        'data\config\config.default.yaml',
        'frontend\index.html',
        'requirements.txt',
        'install-soai-from-release.bat',
        'install-soai-windows.ps1'
    )) {
        $requiredPath = Join-Path $Root $relativePath
        if (!(Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Prepared Windows source is missing: $relativePath"
        }
        $requiredItem = Get-Item -LiteralPath $requiredPath -Force
        if (($requiredItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Prepared Windows source contains a reparse point: $relativePath"
        }
    }
    $runtimeAssets = Join-Path $Root 'runtime-assets'
    $runtimeAssetsRootItem = Get-Item -LiteralPath $runtimeAssets -Force -ErrorAction SilentlyContinue
    if ($null -eq $runtimeAssetsRootItem -or !$runtimeAssetsRootItem.PSIsContainer `
        -or ($runtimeAssetsRootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Prepared Windows source runtime-assets root is missing or unsafe.'
    }
    $runtimeAssetItems = @(Get-ChildItem -LiteralPath $runtimeAssets -Recurse -Force)
    if (@($runtimeAssetItems | Where-Object { !$_.PSIsContainer }).Count -eq 0) {
        throw 'Prepared Windows source runtime-assets tree is empty.'
    }
    foreach ($runtimeAssetItem in $runtimeAssetItems) {
        if (($runtimeAssetItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Prepared Windows source runtime-assets contains a reparse point: $($runtimeAssetItem.FullName)"
        }
        if (!$runtimeAssetItem.PSIsContainer -and !(Test-Path -LiteralPath $runtimeAssetItem.FullName -PathType Leaf)) {
            throw "Prepared Windows source runtime-assets contains a special entry: $($runtimeAssetItem.FullName)"
        }
    }
}

$sourceRoot = Resolve-FullPath $SourceRoot
$versionPath = Join-Path $sourceRoot 'VERSION'
if (!(Test-Path -LiteralPath $versionPath -PathType Leaf)) {
    throw 'Windows source tree lacks VERSION.'
}
$Version = (Get-Content -LiteralPath $versionPath -Raw).Trim()
if ($Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') {
    throw 'Windows source VERSION is invalid.'
}
$dependencyAuthorityPath = Join-Path $PSScriptRoot 'dependencies-v1.json'
$dependencyAuthority = Get-Content -LiteralPath $dependencyAuthorityPath -Raw -Encoding UTF8 | ConvertFrom-Json
$pythonDependency = $dependencyAuthority.dependencies.python
$pythonDependencyFields = @($pythonDependency.PSObject.Properties.Name | Sort-Object)
if ($dependencyAuthority.schema_version -ne 1 `
    -or (Compare-Object $pythonDependencyFields @('package_sha256', 'url', 'version')).Count -ne 0 `
    -or $pythonDependency.version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$' `
    -or $pythonDependency.url -notmatch '^https://' `
    -or $pythonDependency.package_sha256 -notmatch '^[0-9a-f]{64}$') {
    throw 'Windows Python dependency authority is invalid.'
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $PSScriptRoot 'out'
}
$outputRoot = Resolve-FullPath $OutputDir
$launcherOut = Join-Path $outputRoot 'launcher'
$payloadRoot = Join-Path $outputRoot 'payload'
$installerOut = $outputRoot
$installerAssets = Join-Path $PSScriptRoot 'installer\assets'
$installerIcon = Join-Path $installerAssets 'soai-installer.ico'
$releaseRoot = $sourceRoot
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
$outputLockPath = Join-Path $outputRoot '.soai-windows-release.lock'
try {
    $outputLockStream = [System.IO.FileStream]::new(
        $outputLockPath,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None,
        1,
        [System.IO.FileOptions]::DeleteOnClose
    )
} catch [System.IO.IOException] {
    throw "Another Windows release build owns the output lock: $outputLockPath"
}

try {
    Assert-PreparedWindowsSource -Root $releaseRoot -ExpectedVersion $Version
    $expectedInstaller = Join-Path $outputRoot "SoAI-$Version-windows-x64-setup.exe"
    $completeArchive = Join-Path $outputRoot "SoAI-$Version-windows-x64-complete.zip"
    if (Test-Path -LiteralPath $completeArchive) {
        throw "Complete Windows archive already exists: $completeArchive"
    }
    if (!$SkipInstaller -and (Test-Path -LiteralPath $expectedInstaller)) {
        throw "Windows installer already exists: $expectedInstaller"
    }

    New-Item -ItemType Directory -Force -Path $launcherOut, $payloadRoot, $installerOut | Out-Null

    if (!(Test-Path -LiteralPath $installerIcon)) {
        & (Join-Path $PSScriptRoot 'tools\New-InstallerAssets.ps1') `
            -AssetsDir $installerAssets `
            -LogoPath (Join-Path $releaseRoot 'frontend\assets\img\soai\soai-logo-small-dark.png')
    }

    Write-Host "Building SoAI launcher..."
    & (Join-Path $PSScriptRoot 'launcher\build-launcher.ps1') `
        -OutputDir $launcherOut `
        -IconPath $installerIcon `
        -Version $Version
    Write-Host "Staging installer payload..."
    & (Join-Path $PSScriptRoot 'tools\Copy-ReleasePayload.ps1') `
        -SourceRoot $releaseRoot `
        -PayloadDir $payloadRoot `
        -LauncherBuildDir $launcherOut `
        -WindowsReleaseRoot $PSScriptRoot `
        -Version $Version
    $sourceBackground = Join-Path $releaseRoot 'backend\core\bootstrap\background.py'
    $stagedBackground = Join-Path $payloadRoot 'backend\core\bootstrap\background.py'
    Assert-FilesMatch -Source $sourceBackground -Staged $stagedBackground -FailureMessage 'Windows background runtime fix was not staged exactly.'
    $sourceRuntimeInstaller = Join-Path $PSScriptRoot 'installer\scripts\Install-SoAIRuntime.ps1'
    $stagedRuntimeInstaller = Join-Path $payloadRoot 'installer-support\Install-SoAIRuntime.ps1'
    Assert-FilesMatch -Source $sourceRuntimeInstaller -Staged $stagedRuntimeInstaller -FailureMessage 'Windows runtime installer script was not staged exactly.'
    $sourceUpgradePreserver = Join-Path $PSScriptRoot 'installer\scripts\Preserve-SoAIUpgrade.ps1'
    $stagedUpgradePreserver = Join-Path $payloadRoot 'installer-support\Preserve-SoAIUpgrade.ps1'
    Assert-FilesMatch -Source $sourceUpgradePreserver -Staged $stagedUpgradePreserver -FailureMessage 'Windows upgrade preservation script was not staged exactly.'
    $sourceRuntimeAssets = Join-Path $releaseRoot 'runtime-assets'
    $stagedRuntimeAssets = Join-Path $payloadRoot 'runtime-assets'
    $sourceRuntimeFiles = @(Get-ChildItem -LiteralPath $sourceRuntimeAssets -Recurse -File -Force | Sort-Object FullName)
    $stagedRuntimeFiles = @(Get-ChildItem -LiteralPath $stagedRuntimeAssets -Recurse -File -Force | Sort-Object FullName)
    $sourceRelativePaths = @($sourceRuntimeFiles | ForEach-Object {
        $_.FullName.Substring($sourceRuntimeAssets.Length).TrimStart('\')
    })
    $stagedRelativePaths = @($stagedRuntimeFiles | ForEach-Object {
        $_.FullName.Substring($stagedRuntimeAssets.Length).TrimStart('\')
    })
    if ((Compare-Object $sourceRelativePaths $stagedRelativePaths).Count -ne 0) {
        throw 'Windows runtime-assets relative paths changed during payload staging.'
    }
    foreach ($runtimeAssetRelativePath in $sourceRelativePaths) {
        Assert-FilesMatch `
            -Source (Join-Path $sourceRuntimeAssets $runtimeAssetRelativePath) `
            -Staged (Join-Path $stagedRuntimeAssets $runtimeAssetRelativePath) `
            -FailureMessage "Windows runtime asset changed during payload staging: $runtimeAssetRelativePath"
    }

    Write-Host "Building complete Windows archive..."
    & (Join-Path $PSScriptRoot 'tools\New-CompleteArchive.ps1') `
        -PayloadDir $payloadRoot `
        -OutputPath $completeArchive `
        -Version $Version

    if ($SkipInstaller) {
        Write-Host "Skipped NSIS build. Payload is ready at: $payloadRoot"
        return
    }

    Write-Host "Building NSIS installer..."
    $installerArgs = @{
        PayloadDir = $payloadRoot
        OutputDir = $installerOut
        Version = $Version
        NoNSISBootstrap = $NoNSISBootstrap
        PythonVersion = $pythonDependency.version
        PythonUrl = $pythonDependency.url
        PythonSha256 = $pythonDependency.package_sha256
    }
    if ($MakensisPath) {
        $installerArgs.MakensisPath = $MakensisPath
    }
    try {
        & (Join-Path $PSScriptRoot 'installer\build-installer.ps1') @installerArgs
        if (!(Test-Path -LiteralPath $expectedInstaller) -or (Get-Item -LiteralPath $expectedInstaller).Length -le 0) {
            throw "Windows installer was not produced: $expectedInstaller"
        }
    } catch {
        if (Test-Path -LiteralPath $expectedInstaller) {
            Remove-Item -LiteralPath $expectedInstaller -Force
        }
        if (Test-Path -LiteralPath $completeArchive) {
            Remove-Item -LiteralPath $completeArchive -Force
        }
        throw
    }
} finally {
    $outputLockStream.Dispose()
    if (Test-Path -LiteralPath $outputLockPath) {
        Remove-Item -LiteralPath $outputLockPath -Force
    }
}
