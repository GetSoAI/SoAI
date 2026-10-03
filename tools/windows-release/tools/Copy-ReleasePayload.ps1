# SoAI - Windows installer payload assembly
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0
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

Import-Module (Join-Path $PSScriptRoot 'WindowsPayloadFiltering.psm1') -Force
Import-Module (Join-Path $PSScriptRoot 'WindowsPayloadValidation.psm1') -Force

$script:ResolvedSourceRoot = Resolve-FullPath $SourceRoot
$payloadRoot = Assert-SafeGeneratedDirectory $PayloadDir
$launcherRoot = Resolve-FullPath $LauncherBuildDir
$windowsReleaseRoot = Resolve-FullPath $WindowsReleaseRoot

$script:BuiltLauncherRootFiles = @(
    'soai.exe',
    'soai.exe.config',
    'soai-app.ico',
    'Microsoft.Web.WebView2.Core.dll',
    'Microsoft.Web.WebView2.WinForms.dll',
    'WebView2Loader.dll'
)

$runtimeAssetsSource = Join-Path $script:ResolvedSourceRoot 'runtime-assets'
if (!(Test-Path -LiteralPath $runtimeAssetsSource -PathType Container)) {
    throw 'Windows build source lacks the validated runtime-assets tree.'
}
$runtimeAssetItems = @(Get-ChildItem -LiteralPath $runtimeAssetsSource -Recurse -Force)
foreach ($runtimeAssetItem in $runtimeAssetItems) {
    if (($runtimeAssetItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Windows build source runtime-assets contains a reparse point: $($runtimeAssetItem.FullName)"
    }
    if (!$runtimeAssetItem.PSIsContainer -and !(Test-Path -LiteralPath $runtimeAssetItem.FullName -PathType Leaf)) {
        throw "Windows build source runtime-assets contains a special entry: $($runtimeAssetItem.FullName)"
    }
}
$runtimeAssetFiles = @($runtimeAssetItems | Where-Object { !$_.PSIsContainer } | Sort-Object FullName)
if ($runtimeAssetFiles.Count -eq 0) {
    throw 'Windows build source runtime-assets tree is empty.'
}
$runtimeAssetRelativePaths = @($runtimeAssetFiles | ForEach-Object {
    $_.FullName.Substring($runtimeAssetsSource.Length).TrimStart('\')
})

$builtPayloadFiles = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(
    $script:BuiltLauncherRootFiles
    $runtimeAssetRelativePaths | ForEach-Object { "runtime-assets\$_" }
) | ForEach-Object { [void]$builtPayloadFiles.Add($_) }

if (Test-Path -LiteralPath $payloadRoot) {
    Remove-Item -LiteralPath $payloadRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $payloadRoot | Out-Null

Copy-FilteredTree -Source $script:ResolvedSourceRoot -Destination $payloadRoot -SourceRoot $script:ResolvedSourceRoot
Assert-FilteredPayload -PayloadRoot $payloadRoot -BuiltPayloadFiles $builtPayloadFiles
Assert-WindowsPlatformPayload -PayloadRoot $payloadRoot
Assert-WindowsLicenseInventory -PayloadRoot $payloadRoot

$runtimeAssetsDestination = Join-Path $payloadRoot 'runtime-assets'
if (Test-Path -LiteralPath $runtimeAssetsDestination) {
    Remove-Item -LiteralPath $runtimeAssetsDestination -Recurse -Force
}
Copy-Item -LiteralPath $runtimeAssetsSource -Destination $runtimeAssetsDestination -Recurse -Force

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
Copy-Item -LiteralPath (Join-Path $launcherRoot 'soai.exe.config') -Destination $supportDir -Force
Copy-Item -LiteralPath (Join-Path $windowsReleaseRoot 'installer\scripts\Install-SoAIRuntime.ps1') -Destination $supportDir -Force
Copy-Item -LiteralPath (Join-Path $windowsReleaseRoot 'installer\scripts\Admit-SoAIInstall.ps1') -Destination $supportDir -Force
Copy-Item -LiteralPath (Join-Path $windowsReleaseRoot 'dependencies-v1.json') -Destination $supportDir -Force
Copy-Item -LiteralPath (Join-Path $windowsReleaseRoot 'installer\scripts\Remove-SoAI.ps1') -Destination $supportDir -Force
Copy-Item -LiteralPath (Join-Path $windowsReleaseRoot 'installer\scripts\Preserve-SoAIUpgrade.ps1') -Destination $supportDir -Force

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

Assert-FilteredPayload -PayloadRoot $payloadRoot -BuiltPayloadFiles $builtPayloadFiles -PermitBuiltPayloadFiles
Assert-WindowsPlatformPayload -PayloadRoot $payloadRoot
Assert-WindowsLicenseInventory -PayloadRoot $payloadRoot

Write-Host "Payload staged at: $payloadRoot"
