[CmdletBinding()]
param(
    [string]$SourceRoot,
    [string]$OutputDir,
    [string]$MakensisPath,
    [switch]$NoNSISBootstrap,
    [switch]$SkipCompleteArchive,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    $SourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $PSScriptRoot 'out'
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

$releaseRoot = Resolve-FullPath $SourceRoot
$versionPath = Join-Path $releaseRoot 'VERSION'
if (!(Test-Path -LiteralPath $versionPath -PathType Leaf)) {
    throw 'Windows build kit lacks VERSION.'
}
$Version = (Get-Content -LiteralPath $versionPath -Raw).Trim()
if ($Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') {
    throw 'Windows build kit VERSION is invalid.'
}
$outputRoot = Resolve-FullPath $OutputDir
$launcherOut = Join-Path $outputRoot 'launcher'
$payloadRoot = Join-Path $outputRoot 'payload'
$installerOut = $outputRoot
$installerAssets = Join-Path $PSScriptRoot 'installer\assets'
$installerIcon = Join-Path $installerAssets 'soai-installer.ico'
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
    $buildKitMarker = Join-Path $releaseRoot 'WINDOWS-BUILD-KIT.txt'
    if (!(Test-Path -LiteralPath $buildKitMarker)) {
        throw 'SourceRoot must be an extracted SoAI Windows x64 build kit.'
    }
    $releaseInfoPath = Join-Path $releaseRoot 'release-info-v1.json'
    if (!(Test-Path -LiteralPath $releaseInfoPath)) {
        throw 'Windows build kit lacks release-info-v1.json.'
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
        -or $releaseInfo.version -ne $Version `
        -or $releaseInfo.core_version -ne $Version) {
        throw 'Windows build kit release identity is invalid.'
    }
    $completeArchive = Join-Path $outputRoot "SoAI-$Version-windows-x64-complete.zip"
    $temporaryArchive = Join-Path $outputRoot ".SoAI-$Version-windows-x64-complete.partial.zip"
    $expectedInstaller = Join-Path $outputRoot "SoAI-$Version-windows-x64-setup.exe"
    if (!$SkipCompleteArchive -and (Test-Path -LiteralPath $completeArchive)) {
        throw "Complete Windows archive already exists: $completeArchive"
    }
    if (!$SkipCompleteArchive -and (Test-Path -LiteralPath $temporaryArchive)) {
        throw "Partial Windows archive already exists: $temporaryArchive"
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
    foreach ($runtimeAssetName in @('tesseract-5.5.3-windows-x64.zip', 'tesseract-5.5.3-windows-x64.json')) {
        $sourceRuntimeAsset = Join-Path $releaseRoot "runtime-assets\$runtimeAssetName"
        $stagedRuntimeAsset = Join-Path $payloadRoot "runtime-assets\$runtimeAssetName"
        Assert-FilesMatch -Source $sourceRuntimeAsset -Staged $stagedRuntimeAsset -FailureMessage "Windows Tesseract runtime asset was not staged exactly: $runtimeAssetName"
    }

    if ($SkipCompleteArchive) {
        Write-Host "Skipped complete Windows archive build."
    } else {
        $completeStage = Join-Path $outputRoot '.complete-archive-stage'
        if (Test-Path -LiteralPath $completeStage) {
            throw "Complete Windows archive staging path already exists: $completeStage"
        }
        try {
            $completeRoot = Join-Path $completeStage 'SoAI'
            New-Item -ItemType Directory -Path $completeRoot | Out-Null
            Get-ChildItem -LiteralPath $payloadRoot -Force | Copy-Item -Destination $completeRoot -Recurse -Force
            Compress-Archive -LiteralPath $completeRoot -DestinationPath $temporaryArchive -CompressionLevel Optimal
            Move-Item -LiteralPath $temporaryArchive -Destination $completeArchive
        } catch {
            if (Test-Path -LiteralPath $temporaryArchive) {
                Remove-Item -LiteralPath $temporaryArchive -Force
            }
            throw
        } finally {
            if (Test-Path -LiteralPath $completeStage) {
                Remove-Item -LiteralPath $completeStage -Recurse -Force
            }
        }
        Write-Host "Complete Windows archive built at: $completeArchive"
    }

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
        if (!$SkipCompleteArchive -and (Test-Path -LiteralPath $completeArchive)) {
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
