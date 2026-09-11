# SoAI - Canonical Windows complete archive creation [tools/windows-release/tools/New-CompleteArchive.ps1]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PayloadDir,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [Parameter(Mandatory=$true)][string]$Version
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Resolve-FullPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $executionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
}

function Get-RelativeArchivePath {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$Path
    )
    $prefix = $Root.TrimEnd('\') + '\'
    if (!$Path.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Archive member escapes the Windows payload root: $Path"
    }
    return $Path.Substring($prefix.Length).Replace('\', '/')
}

if ($Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') {
    throw "Windows complete archive version is invalid: $Version"
}
$payloadRoot = Resolve-FullPath $PayloadDir
$archivePath = Resolve-FullPath $OutputPath
if (!(Test-Path -LiteralPath $payloadRoot -PathType Container)) {
    throw "Windows payload directory does not exist: $payloadRoot"
}
if (Test-Path -LiteralPath $archivePath) {
    throw "Windows complete archive already exists: $archivePath"
}
$expectedArchiveName = "SoAI-$Version-windows-x64-complete.zip"
if ((Split-Path -Leaf $archivePath) -ne $expectedArchiveName) {
    throw "Windows complete archive name must be $expectedArchiveName."
}

$releaseInfoPath = Join-Path $payloadRoot 'release-info-v1.json'
$releaseInfo = Get-Content -LiteralPath $releaseInfoPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($releaseInfo.schema_version -ne 1 `
    -or $releaseInfo.product -ne 'SoAI' `
    -or $releaseInfo.edition -ne 'soai-core' `
    -or $releaseInfo.artifact_type -ne 'complete' `
    -or $releaseInfo.version -ne $Version `
    -or $releaseInfo.core_version -ne $Version) {
    throw 'Windows complete payload release identity is invalid.'
}
foreach ($requiredPath in @(
    'soai.exe',
    'install-soai-from-release.bat',
    'install-soai-windows.ps1',
    'Microsoft.Web.WebView2.Core.dll',
    'Microsoft.Web.WebView2.WinForms.dll',
    'WebView2Loader.dll',
    'installer-support\Install-SoAIRuntime.ps1',
    'installer-support\Remove-SoAI.ps1',
    'installer-support\installed-files.txt'
)) {
    if (!(Test-Path -LiteralPath (Join-Path $payloadRoot $requiredPath) -PathType Leaf)) {
        throw "Windows complete payload is missing: $requiredPath"
    }
}

$files = @(Get-ChildItem -LiteralPath $payloadRoot -Recurse -File -Force)
if ($files.Count -eq 0) {
    throw 'Windows complete payload contains no files.'
}
$relativePaths = New-Object System.Collections.Generic.List[string]
$normalizedPaths = New-Object System.Collections.Generic.HashSet[string]([System.StringComparer]::OrdinalIgnoreCase)
$fileByRelativePath = @{}
foreach ($file in $files) {
    if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Windows complete payload contains a reparse point: $($file.FullName)"
    }
    $relativePath = Get-RelativeArchivePath -Root $payloadRoot -Path $file.FullName
    $normalizedPath = $relativePath.Normalize([Text.NormalizationForm]::FormC)
    if (!$normalizedPaths.Add($normalizedPath)) {
        throw "Windows complete payload paths collide by case or Unicode: $relativePath"
    }
    [void]$relativePaths.Add($relativePath)
    $fileByRelativePath[$relativePath] = $file.FullName
}
$orderedPaths = $relativePaths.ToArray()
$sortKeys = [string[]]::new($orderedPaths.Length)
for ($pathIndex = 0; $pathIndex -lt $orderedPaths.Length; $pathIndex += 1) {
    $sortKeys[$pathIndex] = $orderedPaths[$pathIndex].Replace('/', [char]0)
}
[Array]::Sort($sortKeys, $orderedPaths, [System.StringComparer]::Ordinal)

$archiveParent = Split-Path -Parent $archivePath
if (!(Test-Path -LiteralPath $archiveParent -PathType Container)) {
    throw "Windows complete archive parent does not exist: $archiveParent"
}
$temporaryArchive = Join-Path $archiveParent ("." + $expectedArchiveName + "." + [Guid]::NewGuid().ToString('N') + ".partial")
try {
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archiveStream = [IO.File]::Open(
        $temporaryArchive,
        [IO.FileMode]::CreateNew,
        [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::None
    )
    try {
        $archive = [IO.Compression.ZipArchive]::new(
            $archiveStream,
            [IO.Compression.ZipArchiveMode]::Create,
            $false,
            [Text.Encoding]::UTF8
        )
        try {
            foreach ($relativePath in $orderedPaths) {
                $entry = $archive.CreateEntry(
                    "SoAI/$relativePath",
                    [IO.Compression.CompressionLevel]::Optimal
                )
                $entry.LastWriteTime = [DateTimeOffset]::new(1980, 1, 1, 0, 0, 0, [TimeSpan]::Zero)
                $entry.ExternalAttributes = -2119958528
                $sourceStream = [IO.File]::Open(
                    $fileByRelativePath[$relativePath],
                    [IO.FileMode]::Open,
                    [IO.FileAccess]::Read,
                    [IO.FileShare]::Read
                )
                $entryStream = $entry.Open()
                try {
                    $sourceStream.CopyTo($entryStream)
                }
                finally {
                    $entryStream.Dispose()
                    $sourceStream.Dispose()
                }
            }
        }
        finally {
            $archive.Dispose()
        }
    }
    finally {
        $archiveStream.Dispose()
    }
    if ((Get-Item -LiteralPath $temporaryArchive).Length -le 0) {
        throw 'Windows complete archive is empty.'
    }
    Move-Item -LiteralPath $temporaryArchive -Destination $archivePath
}
finally {
    if (Test-Path -LiteralPath $temporaryArchive) {
        Remove-Item -LiteralPath $temporaryArchive -Force
    }
}

Write-Host "Complete Windows archive built at: $archivePath"
