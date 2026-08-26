[CmdletBinding()]
param(
    [string]$OutputDir,
    [string]$IconPath,
    [string]$WebView2PackageDir,
    [Parameter(Mandatory=$true)][string]$Version,
    [string]$Configuration = 'Release'
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $PSScriptRoot '..\out\launcher'
}

function Resolve-FullPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $executionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
}

function Find-CSharpCompiler {
    $candidates = @(
        "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
        "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    throw 'The .NET Framework C# compiler was not found. Install the .NET Framework developer tools on the Windows release machine.'
}

function Find-WebView2Package {
    param([string]$ExplicitPath)
    if ($ExplicitPath) {
        $resolved = Resolve-FullPath $ExplicitPath
        if (Test-Path -LiteralPath (Join-Path $resolved 'lib\net462\Microsoft.Web.WebView2.Core.dll')) {
            return $resolved
        }
        throw "The supplied WebView2 package path is invalid: $resolved"
    }

    $dependencyManifestPath = Join-Path $PSScriptRoot '..\dependencies-v1.json'
    $dependencyManifest = Get-Content -LiteralPath $dependencyManifestPath -Raw | ConvertFrom-Json
    if ($dependencyManifest.schema_version -ne 1) {
        throw 'Windows release dependency manifest is invalid.'
    }
    $webView2Dependency = $dependencyManifest.dependencies.webview2_sdk
    if ([string]::IsNullOrWhiteSpace($webView2Dependency.url) -or [string]::IsNullOrWhiteSpace($webView2Dependency.version) -or $webView2Dependency.package_sha256 -notmatch '^[a-fA-F0-9]{64}$') {
        throw 'WebView2 SDK dependency manifest entry is invalid.'
    }

    $cacheRoot = Join-Path $PSScriptRoot '..\out\cache'
    $packageRoot = Join-Path $cacheRoot 'Microsoft.Web.WebView2'
    New-Item -ItemType Directory -Force -Path $cacheRoot | Out-Null
    $nupkg = Join-Path $cacheRoot 'Microsoft.Web.WebView2.nupkg'
    $zip = Join-Path $cacheRoot 'Microsoft.Web.WebView2.zip'
    if (!(Test-Path -LiteralPath $nupkg -PathType Leaf)) {
        Write-Host "Downloading Microsoft.Web.WebView2 SDK..."
        Invoke-WebRequest -Uri $webView2Dependency.url -OutFile $nupkg -UseBasicParsing
    }
    $actualHash = (Get-FileHash -LiteralPath $nupkg -Algorithm SHA256).Hash
    if (![string]::Equals($actualHash, $webView2Dependency.package_sha256, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Cached WebView2 SDK package failed SHA-256 verification.'
    }
    Copy-Item -LiteralPath $nupkg -Destination $zip -Force
    if (Test-Path -LiteralPath $packageRoot) {
        Remove-Item -LiteralPath $packageRoot -Recurse -Force
    }
    Expand-Archive -LiteralPath $zip -DestinationPath $packageRoot -Force
    if (!(Test-Path -LiteralPath (Join-Path $packageRoot 'lib\net462\Microsoft.Web.WebView2.Core.dll'))) {
        throw 'Downloaded WebView2 SDK package did not contain the expected net462 assemblies.'
    }
    [xml]$packageMetadata = Get-Content -LiteralPath (Join-Path $packageRoot 'Microsoft.Web.WebView2.nuspec') -Raw
    if ([string]$packageMetadata.package.metadata.version -ne [string]$webView2Dependency.version) {
        throw 'WebView2 SDK package version contradicts the dependency manifest.'
    }
    return $packageRoot
}

$outputRoot = Resolve-FullPath $OutputDir
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

$source = Join-Path $PSScriptRoot 'src\SoAILauncher.cs'
$manifestTemplate = Join-Path $PSScriptRoot 'src\soai.exe.manifest.in'
$manifest = Join-Path $outputRoot 'soai.exe.manifest'
$versionParts = @($Version.Split('.'))
$invalidVersionParts = @($versionParts | Where-Object { $_ -notmatch '^[0-9]{1,5}$' -or [int]$_ -gt 65535 })
if ($versionParts.Count -ne 3 -or $invalidVersionParts.Count -gt 0) {
    throw 'Launcher version must contain exactly three numeric components.'
}
$versionQuad = "$Version.0"
$manifestContent = (Get-Content -LiteralPath $manifestTemplate -Raw).Replace('@SOAI_VERSION_QUAD@', $versionQuad)
Set-Content -LiteralPath $manifest -Value $manifestContent -Encoding UTF8
$webView2Package = Find-WebView2Package $WebView2PackageDir
$csc = Find-CSharpCompiler
$outExe = Join-Path $outputRoot 'soai.exe'

$references = @(
    '/reference:System.dll',
    '/reference:System.Core.dll',
    '/reference:System.Drawing.dll',
    '/reference:System.Windows.Forms.dll',
    '/reference:System.Web.Extensions.dll',
    "/reference:$($webView2Package)\lib\net462\Microsoft.Web.WebView2.Core.dll",
    "/reference:$($webView2Package)\lib\net462\Microsoft.Web.WebView2.WinForms.dll"
)

$args = @(
    '/nologo',
    '/target:winexe',
    '/platform:x64',
    '/optimize+',
    "/win32manifest:$manifest",
    "/out:$outExe"
) + $references + @($source)

if ($IconPath -and (Test-Path -LiteralPath $IconPath)) {
    $args = @(
        '/nologo',
        '/target:winexe',
        '/platform:x64',
        '/optimize+',
        "/win32icon:$IconPath",
        "/win32manifest:$manifest",
        "/out:$outExe"
    ) + $references + @($source)
}

& $csc @args
if ($LASTEXITCODE -ne 0) {
    throw "Launcher compilation failed with exit code $LASTEXITCODE."
}

Copy-Item -LiteralPath (Join-Path $webView2Package 'lib\net462\Microsoft.Web.WebView2.Core.dll') -Destination $outputRoot -Force
Copy-Item -LiteralPath (Join-Path $webView2Package 'lib\net462\Microsoft.Web.WebView2.WinForms.dll') -Destination $outputRoot -Force
Copy-Item -LiteralPath (Join-Path $webView2Package 'runtimes\win-x64\native\WebView2Loader.dll') -Destination $outputRoot -Force
if ($IconPath -and (Test-Path -LiteralPath $IconPath)) {
    Copy-Item -LiteralPath $IconPath -Destination (Join-Path $outputRoot 'soai-app.ico') -Force
}

Write-Host "Launcher built at: $outExe"
