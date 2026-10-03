[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PayloadDir,
    [string]$OutputDir,
    [Parameter(Mandatory=$true)][string]$Version,
    [string]$MakensisPath,
    [switch]$NoNSISBootstrap,
    [Parameter(Mandatory=$true)][string]$PythonVersion,
    [Parameter(Mandatory=$true)][string]$PythonUrl,
    [Parameter(Mandatory=$true)][string]$PythonSha256,
    [string]$WebView2BootstrapperUrl = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703',
    [int]$RuntimeFootprintReserveMb = 3000
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $PSScriptRoot '..\out\installer'
}

function Resolve-FullPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $executionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
}

function Resolve-Makensis {
    param(
        [string]$ExplicitPath,
        [switch]$NoBootstrap
    )
    if ($ExplicitPath) {
        $resolved = Resolve-FullPath $ExplicitPath
        if (!(Test-Path -LiteralPath $resolved)) {
            throw "makensis.exe was not found: $resolved"
        }
        return $resolved
    }
    if (![string]::IsNullOrWhiteSpace($env:SOAI_MAKENSIS_PATH)) {
        $resolved = Resolve-FullPath $env:SOAI_MAKENSIS_PATH
        if (!(Test-Path -LiteralPath $resolved)) {
            throw "SOAI_MAKENSIS_PATH points to a missing makensis.exe: $resolved"
        }
        return $resolved
    }
    $bootstrap = Join-Path $PSScriptRoot '..\tools\Bootstrap-NSIS.ps1'
    return (& $bootstrap -NoDownload:$NoBootstrap).Trim()
}

function Convert-ToVersionQuad {
    param([Parameter(Mandatory=$true)][string]$Value)
    $parts = @($Value.Split('.'))
    $invalidParts = @($parts | Where-Object { $_ -notmatch '^[0-9]{1,5}$' -or [int]$_ -gt 65535 })
    if ($parts.Count -ne 3 -or $invalidParts.Count -gt 0) {
        throw 'Installer version must contain exactly three numeric components from 0 through 65535.'
    }
    return "$Value.0"
}

$payloadRoot = Resolve-FullPath $PayloadDir
$outputRoot = Resolve-FullPath $OutputDir
if (!(Test-Path -LiteralPath $payloadRoot)) {
    throw "Payload directory does not exist: $payloadRoot"
}
if (!(Test-Path -LiteralPath (Join-Path $payloadRoot 'soai.exe'))) {
    throw 'Payload is missing soai.exe. Build the launcher before building the installer.'
}
if (!(Test-Path -LiteralPath (Join-Path $payloadRoot 'LICENSE.md'))) {
    throw 'Payload is missing LICENSE.md, which is used by the installer license page.'
}

$assetsDir = Join-Path $PSScriptRoot 'assets'
if (!(Test-Path -LiteralPath (Join-Path $assetsDir 'soai-installer.ico'))) {
    & (Join-Path $PSScriptRoot '..\tools\New-InstallerAssets.ps1') `
        -AssetsDir $assetsDir `
        -LogoPath (Join-Path $payloadRoot 'frontend\assets\img\soai\soai-logo-small-dark.png')
}

New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
$makensis = Resolve-Makensis -ExplicitPath $MakensisPath -NoBootstrap:$NoNSISBootstrap

$licenseFile = Join-Path $outputRoot 'LICENSE.nsis.txt'
$licenseText = Get-Content -LiteralPath (Join-Path $payloadRoot 'LICENSE.md') -Raw -Encoding UTF8
Set-Content -LiteralPath $licenseFile -Value $licenseText -Encoding Unicode

$payloadSizeKb = [int][Math]::Ceiling(((Get-ChildItem -LiteralPath $payloadRoot -Recurse -File | Measure-Object Length -Sum).Sum) / 1KB)
$runtimeFootprintReserveKb = $RuntimeFootprintReserveMb * 1024
$estimatedSizeKb = $payloadSizeKb + $runtimeFootprintReserveKb
$outputFile = Join-Path $outputRoot "SoAI-$Version-windows-x64-setup.exe"
if (Test-Path -LiteralPath $outputFile) {
    throw "Installer output already exists: $outputFile"
}
$versionQuad = Convert-ToVersionQuad $Version
$script = Join-Path $PSScriptRoot 'soai-installer.nsi'
$payloadInclude = Join-Path $outputRoot 'payload-files.nsh'
$maximumPayloadRelativeLength = 0
foreach ($file in Get-ChildItem -LiteralPath $payloadRoot -Recurse -File -Force) {
    $relativeLength = $file.FullName.Substring($payloadRoot.TrimEnd('\').Length + 1).Length
    $maximumPayloadRelativeLength = [Math]::Max($maximumPayloadRelativeLength, $relativeLength)
}
$payloadInstructions = @('StrCpy $InstallerCreateDirectories 1')
foreach ($directory in Get-ChildItem -LiteralPath $payloadRoot -Directory -Recurse -Force | Sort-Object FullName) {
    $relative = $directory.FullName.Substring($payloadRoot.TrimEnd('\').Length + 1)
    $escapedRelative = $relative.Replace('$', '$$')
    $payloadInstructions += 'Push "$INSTDIR\' + $escapedRelative + '"'
    $payloadInstructions += 'Call RetainInstallerAncestors'
    $payloadInstructions += 'StrCmp $InstallFailed 1 install_failed'
}
$payloadInstructions += 'StrCpy $InstallerCreateDirectories 0'
$payloadInstructions += 'ClearErrors'
$payloadInstructions += 'SetOverwrite try'
foreach ($file in Get-ChildItem -LiteralPath $payloadRoot -File -Recurse -Force | Sort-Object FullName) {
    $relative = $file.FullName.Substring($payloadRoot.TrimEnd('\').Length + 1)
    if ($relative -in @('soai.exe', 'soai.exe.config')) { continue }
    $escapedRelative = $relative.Replace('$', '$$')
    $sizeSuffix = ''
    if ($file.Length -ge 1MB) {
        $sizeSuffix = [string]::Format([Globalization.CultureInfo]::InvariantCulture, ' ({0:0.0} MB)', $file.Length / 1MB)
    }
    $payloadInstructions += 'StrCpy $InstallerPayloadEntry "' + $escapedRelative + '"'
    $payloadInstructions += 'SetDetailsPrint both'
    $payloadInstructions += 'DetailPrint "Extract: $InstallerPayloadEntry' + $sizeSuffix + '"'
    $payloadInstructions += 'SetDetailsPrint none'
    $payloadInstructions += 'File "/oname=$InstallerFilesystemRoot\$InstallerPayloadEntry" "${PAYLOAD_DIR}\' + $relative + '"'
    $payloadInstructions += 'IfErrors payload_file_failed'
}
$payloadInstructions += 'SetOverwrite on'
Set-Content -LiteralPath $payloadInclude -Value $payloadInstructions -Encoding Unicode

$defines = @(
    "/DPRODUCT_VERSION=$Version",
    "/DPRODUCT_VERSION_QUAD=$versionQuad",
    "/DPAYLOAD_DIR=$payloadRoot",
    "/DPAYLOAD_FILES_INCLUDE=$payloadInclude",
    "/DPAYLOAD_MAX_RELATIVE_LENGTH=$maximumPayloadRelativeLength",
    "/DOUTPUT_FILE=$outputFile",
    "/DLICENSE_FILE=$licenseFile",
    "/DESTIMATED_SIZE_KB=$estimatedSizeKb",
    "/DRUNTIME_FOOTPRINT_RESERVE_KB=$runtimeFootprintReserveKb",
    "/DPYTHON_VERSION=$PythonVersion",
    "/DPYTHON_URL=$PythonUrl",
    "/DPYTHON_SHA256=$PythonSha256",
    "/DWEBVIEW2_BOOTSTRAPPER_URL=$WebView2BootstrapperUrl"
)

& $makensis /V3 @defines $script
if ($LASTEXITCODE -ne 0) {
    throw "NSIS build failed with exit code $LASTEXITCODE."
}
Write-Host "Installer built at: $outputFile"
