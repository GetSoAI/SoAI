[CmdletBinding()]
param(
    [string]$CacheDir,
    [switch]$NoDownload
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($CacheDir)) {
    $CacheDir = Join-Path $PSScriptRoot '..\out\cache\nsis'
}

function Get-DirectorySha256 {
    param([Parameter(Mandatory=$true)][string]$Root)
    $resolvedRoot = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')
    $records = [System.Collections.Generic.List[string]]::new()
    foreach ($file in Get-ChildItem -LiteralPath $resolvedRoot -Recurse -File -Force) {
        $relativePath = $file.FullName.Substring($resolvedRoot.Length + 1).Replace('\', '/')
        $fileHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $records.Add("$relativePath`0$fileHash`n")
    }
    $values = $records.ToArray()
    [Array]::Sort($values, [System.StringComparer]::Ordinal)
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes([string]::Concat($values))
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($sha256.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha256.Dispose()
    }
}

function Get-ExistingMakensis {
    param([Parameter(Mandatory=$true)][string]$ExpectedBundledTreeHash)
    $bundledRoot = Join-Path $PSScriptRoot 'nsis\nsis-3.11'
    $bundledCandidates = @(
        (Join-Path $bundledRoot 'Bin\makensis.exe'),
        (Join-Path $bundledRoot 'makensis.exe')
    )
    foreach ($candidate in $bundledCandidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $actualBundledTreeHash = Get-DirectorySha256 -Root $bundledRoot
            if (![string]::Equals($actualBundledTreeHash, $ExpectedBundledTreeHash, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw 'Bundled NSIS toolchain failed whole-tree SHA-256 verification.'
            }
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    $command = Get-Command makensis.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $candidates = @(
        "$env:ProgramFiles\NSIS\makensis.exe",
        "${env:ProgramFiles(x86)}\NSIS\makensis.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    return $null
}

function Test-ZipHeader {
    param([Parameter(Mandatory=$true)][string]$Path)
    if (!(Test-Path -LiteralPath $Path)) {
        return $false
    }
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        if ($stream.Length -lt 4) {
            return $false
        }
        $bytes = New-Object byte[] 4
        [void]$stream.Read($bytes, 0, 4)
        return $bytes[0] -eq 0x50 -and $bytes[1] -eq 0x4b
    }
    finally {
        $stream.Dispose()
    }
}

function Assert-Sha256 {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$ExpectedHash
    )
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    if (![string]::Equals($actual, $ExpectedHash, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "SHA-256 mismatch for $Path. Expected $ExpectedHash but got $actual."
    }
}

$dependencyManifestPath = Join-Path $PSScriptRoot '..\dependencies-v1.json'
$dependencyManifest = Get-Content -LiteralPath $dependencyManifestPath -Raw | ConvertFrom-Json
$dependency = $dependencyManifest.dependencies.nsis_portable
if ($dependencyManifest.schema_version -ne 1 -or $dependency.bundled_tree_sha256 -notmatch '^[a-fA-F0-9]{64}$' -or $dependency.package_sha256 -notmatch '^[a-fA-F0-9]{64}$' -or $dependency.embedded_archive_sha256 -notmatch '^[a-fA-F0-9]{64}$') {
    throw 'NSIS dependency manifest entry is invalid.'
}

$existing = Get-ExistingMakensis -ExpectedBundledTreeHash $dependency.bundled_tree_sha256
if ($existing) {
    Write-Output $existing
    return
}

if ($NoDownload) {
    throw 'makensis.exe was not found. Install NSIS 3.x or pass -MakensisPath to installer\build-installer.ps1.'
}

New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null
$portablePackage = Join-Path $CacheDir "nsis.portable.$($dependency.version).nupkg"
$portableZip = Join-Path $CacheDir "nsis.portable.$($dependency.version).zip"
$portableDir = Join-Path $CacheDir "nsis.portable.$($dependency.version)"
$zip = Join-Path $CacheDir "nsis-$($dependency.version).zip"
$extractDir = Join-Path $CacheDir "nsis-$($dependency.version)"
Write-Host 'Downloading pinned nsis.portable package...'
Invoke-WebRequest -Uri $dependency.url -OutFile $portablePackage -UseBasicParsing -MaximumRedirection 10
Assert-Sha256 -Path $portablePackage -ExpectedHash $dependency.package_sha256
Copy-Item -LiteralPath $portablePackage -Destination $portableZip -Force
if (Test-Path -LiteralPath $portableDir) {
    Remove-Item -LiteralPath $portableDir -Recurse -Force
}
Expand-Archive -LiteralPath $portableZip -DestinationPath $portableDir -Force
$embeddedZip = Join-Path $portableDir 'tools\nsis-3.11.zip'
if (!(Test-ZipHeader $embeddedZip)) {
    throw 'Pinned nsis.portable package did not contain a valid NSIS zip.'
}
Assert-Sha256 -Path $embeddedZip -ExpectedHash $dependency.embedded_archive_sha256
Copy-Item -LiteralPath $embeddedZip -Destination $zip -Force

if (Test-Path -LiteralPath $extractDir) {
    Remove-Item -LiteralPath $extractDir -Recurse -Force
}
Expand-Archive -LiteralPath $zip -DestinationPath $extractDir -Force
$makensis = Get-ChildItem -LiteralPath $extractDir -Recurse -Filter makensis.exe | Select-Object -First 1
if (!$makensis) {
    throw 'NSIS archive did not contain makensis.exe.'
}
Write-Output $makensis.FullName
