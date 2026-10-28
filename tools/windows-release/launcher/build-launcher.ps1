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
    param([switch]$Optional)
    $candidates = @(
        "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
        "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    if ($Optional) {
        return $null
    }
    throw 'The .NET Framework C# compiler was not found. Install the .NET Framework developer tools on the Windows release machine.'
}

function Test-CSharpCompilerApi {
    return $null -ne ('Microsoft.CodeAnalysis.CSharp.CSharpCompilation' -as [type])
}

function Get-DependencyManifestEntry {
    param([Parameter(Mandatory=$true)][string]$Name)
    $dependencyManifestPath = Join-Path $PSScriptRoot '..\dependencies-v1.json'
    $dependencyManifest = Get-Content -LiteralPath $dependencyManifestPath -Raw | ConvertFrom-Json
    if ($dependencyManifest.schema_version -ne 1) {
        throw 'Windows release dependency manifest is invalid.'
    }
    return $dependencyManifest.dependencies.$Name
}

function Expand-VerifiedNuGetPackage {
    param(
        [Parameter(Mandatory=$true)][string]$DependencyName,
        [Parameter(Mandatory=$true)][string]$PackageId,
        [Parameter(Mandatory=$true)][string]$DisplayName,
        [Parameter(Mandatory=$true)][string]$RequiredFile,
        [Parameter(Mandatory=$true)][string]$CachePath
    )
    $dependency = Get-DependencyManifestEntry -Name $DependencyName
    if ([string]::IsNullOrWhiteSpace($dependency.url) -or [string]::IsNullOrWhiteSpace($dependency.version) -or $dependency.package_sha256 -notmatch '^[a-fA-F0-9]{64}$') {
        throw "$DisplayName dependency manifest entry is invalid."
    }

    $cacheRoot = Resolve-FullPath $CachePath
    $packageRoot = Join-Path $cacheRoot $PackageId
    New-Item -ItemType Directory -Force -Path $cacheRoot | Out-Null
    $nupkg = Join-Path $cacheRoot "$PackageId.nupkg"
    $zip = Join-Path $cacheRoot "$PackageId.zip"
    if (!(Test-Path -LiteralPath $nupkg -PathType Leaf)) {
        Write-Host "Downloading $PackageId..."
        Invoke-WebRequest -Uri $dependency.url -OutFile $nupkg -UseBasicParsing
    }
    $actualHash = (Get-FileHash -LiteralPath $nupkg -Algorithm SHA256).Hash
    if (![string]::Equals($actualHash, $dependency.package_sha256, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Cached $DisplayName package failed SHA-256 verification."
    }
    Copy-Item -LiteralPath $nupkg -Destination $zip -Force
    if (Test-Path -LiteralPath $packageRoot) {
        Remove-Item -LiteralPath $packageRoot -Recurse -Force
    }
    Expand-Archive -LiteralPath $zip -DestinationPath $packageRoot -Force
    if (!(Test-Path -LiteralPath (Join-Path $packageRoot $RequiredFile) -PathType Leaf)) {
        throw "Downloaded $DisplayName package did not contain $RequiredFile."
    }
    [xml]$packageMetadata = Get-Content -LiteralPath (Join-Path $packageRoot "$PackageId.nuspec") -Raw
    if ([string]$packageMetadata.package.metadata.version -ne [string]$dependency.version) {
        throw "$DisplayName package version contradicts the dependency manifest."
    }
    return $packageRoot
}

function Find-WebView2Package {
    param(
        [string]$ExplicitPath,
        [Parameter(Mandatory=$true)][string]$CachePath
    )
    if ($ExplicitPath) {
        $resolved = Resolve-FullPath $ExplicitPath
        if (Test-Path -LiteralPath (Join-Path $resolved 'lib\net462\Microsoft.Web.WebView2.Core.dll')) {
            return $resolved
        }
        throw "The supplied WebView2 package path is invalid: $resolved"
    }
    return Expand-VerifiedNuGetPackage `
        -DependencyName 'webview2_sdk' `
        -PackageId 'Microsoft.Web.WebView2' `
        -DisplayName 'WebView2 SDK' `
        -RequiredFile 'lib\net462\Microsoft.Web.WebView2.Core.dll' `
        -CachePath $CachePath
}

function Invoke-CSharpCompilerApi {
    param(
        [Parameter(Mandatory=$true)][string[]]$SourcePaths,
        [Parameter(Mandatory=$true)][string]$ManifestPath,
        [string]$IconPath,
        [Parameter(Mandatory=$true)][string]$OutputPath,
        [Parameter(Mandatory=$true)][string[]]$ReferencePaths
    )
    # Hosts without the .NET Framework compiler, such as the Wine release builder, use the
    # Roslyn compiler bundled with PowerShell 7 against pinned .NET Framework reference
    # assemblies. C# 5 keeps the source compatible with the .NET Framework csc.exe path.
    $references = [System.Collections.Generic.List[Microsoft.CodeAnalysis.MetadataReference]]::new()
    foreach ($referencePath in $ReferencePaths) {
        if (!(Test-Path -LiteralPath $referencePath -PathType Leaf)) {
            throw "Launcher compilation reference is missing: $referencePath"
        }
        $references.Add([Microsoft.CodeAnalysis.MetadataReference]::CreateFromFile($referencePath))
    }
    $parseOptions = [Microsoft.CodeAnalysis.CSharp.CSharpParseOptions]::new(
        [Microsoft.CodeAnalysis.CSharp.LanguageVersion]::CSharp5
    )
    $syntaxTrees = [System.Collections.Generic.List[Microsoft.CodeAnalysis.SyntaxTree]]::new()
    foreach ($sourcePath in $SourcePaths) {
        $sourceText = [Microsoft.CodeAnalysis.Text.SourceText]::From(
            [IO.File]::ReadAllText($sourcePath),
            [Text.Encoding]::UTF8
        )
        $syntaxTrees.Add([Microsoft.CodeAnalysis.CSharp.CSharpSyntaxTree]::ParseText($sourceText, $parseOptions, $sourcePath))
    }
    $compilationOptions = [Microsoft.CodeAnalysis.CSharp.CSharpCompilationOptions]::new(
        [Microsoft.CodeAnalysis.OutputKind]::WindowsApplication
    ).WithOptimizationLevel(
        [Microsoft.CodeAnalysis.OptimizationLevel]::Release
    ).WithPlatform(
        [Microsoft.CodeAnalysis.Platform]::X64
    ).WithDeterministic($true)
    $compilation = [Microsoft.CodeAnalysis.CSharp.CSharpCompilation]::Create(
        [IO.Path]::GetFileNameWithoutExtension($OutputPath),
        $syntaxTrees,
        $references,
        $compilationOptions
    )
    $manifestStream = [IO.File]::OpenRead($ManifestPath)
    $iconStream = $null
    $outputStream = $null
    try {
        if ($IconPath -and (Test-Path -LiteralPath $IconPath)) {
            $iconStream = [IO.File]::OpenRead($IconPath)
        }
        $win32Resources = $compilation.CreateDefaultWin32Resources($true, $false, $manifestStream, $iconStream)
        $outputStream = [IO.File]::Open($OutputPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $result = $compilation.Emit($outputStream, $null, $null, $win32Resources)
    }
    finally {
        foreach ($stream in @($outputStream, $iconStream, $manifestStream)) {
            if ($null -ne $stream) {
                $stream.Dispose()
            }
        }
    }
    foreach ($diagnostic in $result.Diagnostics) {
        if ($diagnostic.Severity -ge [Microsoft.CodeAnalysis.DiagnosticSeverity]::Warning) {
            Write-Host $diagnostic.ToString()
        }
    }
    if (!$result.Success) {
        Remove-Item -LiteralPath $OutputPath -Force -ErrorAction SilentlyContinue
        throw 'Launcher compilation failed.'
    }
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
$dependencyCacheRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    'SoAI-Windows-Launcher-' + [Guid]::NewGuid().ToString('N')
)
try {
    New-Item -ItemType Directory -Force -Path $dependencyCacheRoot | Out-Null
    $assemblyInfo = Join-Path $dependencyCacheRoot 'SoAILauncher.AssemblyInfo.cs'
    $assemblyInfoContent = @(
        'using System.Reflection;',
        '[assembly: AssemblyTitle("SoAI")]',
        '[assembly: AssemblyProduct("SoAI Core")]',
        '[assembly: AssemblyCompany("SoAI")]',
        '[assembly: AssemblyCopyright("Copyright \u00A9 SoAI")]',
        "[assembly: AssemblyVersion(""$versionQuad"")]",
        "[assembly: AssemblyFileVersion(""$versionQuad"")]",
        "[assembly: AssemblyInformationalVersion(""$Version"")]"
    ) -join "`r`n"
    Set-Content -LiteralPath $assemblyInfo -Value $assemblyInfoContent -Encoding UTF8
    $webView2Package = Find-WebView2Package `
        -ExplicitPath $WebView2PackageDir `
        -CachePath $dependencyCacheRoot
    $csc = Find-CSharpCompiler -Optional
    if (!$csc -and !(Test-CSharpCompilerApi)) {
        $csc = Find-CSharpCompiler
    }
    $outExe = Join-Path $outputRoot 'soai.exe'
    $webView2References = @(
        "$($webView2Package)\lib\net462\Microsoft.Web.WebView2.Core.dll",
        "$($webView2Package)\lib\net462\Microsoft.Web.WebView2.WinForms.dll"
    )

    if ($csc) {
        Write-Host "Compiling launcher with the .NET Framework C# compiler: $csc"
        $references = @(
            '/reference:System.dll',
            '/reference:System.Core.dll',
            '/reference:System.Drawing.dll',
            '/reference:System.ServiceProcess.dll',
            '/reference:System.Windows.Forms.dll',
            '/reference:System.Web.Extensions.dll'
        ) + @($webView2References | ForEach-Object { "/reference:$_" })

        $args = @(
            '/nologo',
            '/target:winexe',
            '/platform:x64',
            '/optimize+',
            "/win32manifest:$manifest",
            "/out:$outExe"
        ) + $references + @($source, $assemblyInfo)

        if ($IconPath -and (Test-Path -LiteralPath $IconPath)) {
            $args = @(
                '/nologo',
                '/target:winexe',
                '/platform:x64',
                '/optimize+',
                "/win32icon:$IconPath",
                "/win32manifest:$manifest",
                "/out:$outExe"
            ) + $references + @($source, $assemblyInfo)
        }

        & $csc @args
        if ($LASTEXITCODE -ne 0) {
            throw "Launcher compilation failed with exit code $LASTEXITCODE."
        }
    } else {
        $referenceAssemblies = Expand-VerifiedNuGetPackage `
            -DependencyName 'netfx_reference_assemblies' `
            -PackageId 'Microsoft.NETFramework.ReferenceAssemblies.net48' `
            -DisplayName '.NET Framework reference assemblies' `
            -RequiredFile 'build\.NETFramework\v4.8\mscorlib.dll' `
            -CachePath $dependencyCacheRoot
        $referenceRoot = Join-Path $referenceAssemblies 'build\.NETFramework\v4.8'
        $referencePaths = @(@(
            'mscorlib.dll',
            'System.dll',
            'System.Core.dll',
            'System.Drawing.dll',
            'System.ServiceProcess.dll',
            'System.Windows.Forms.dll',
            'System.Web.Extensions.dll'
        ) | ForEach-Object { Join-Path $referenceRoot $_ }) + $webView2References
        Write-Host 'Compiling launcher with the PowerShell Roslyn compiler and pinned .NET Framework 4.8 reference assemblies.'
        Invoke-CSharpCompilerApi `
            -SourcePaths @($source, $assemblyInfo) `
            -ManifestPath $manifest `
            -IconPath $IconPath `
            -OutputPath $outExe `
            -ReferencePaths $referencePaths
    }

    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'src\soai.exe.config') -Destination $outputRoot -Force
    Copy-Item -LiteralPath (Join-Path $webView2Package 'lib\net462\Microsoft.Web.WebView2.Core.dll') -Destination $outputRoot -Force
    Copy-Item -LiteralPath (Join-Path $webView2Package 'lib\net462\Microsoft.Web.WebView2.WinForms.dll') -Destination $outputRoot -Force
    Copy-Item -LiteralPath (Join-Path $webView2Package 'runtimes\win-x64\native\WebView2Loader.dll') -Destination $outputRoot -Force
    if ($IconPath -and (Test-Path -LiteralPath $IconPath)) {
        Copy-Item -LiteralPath $IconPath -Destination (Join-Path $outputRoot 'soai-app.ico') -Force
    }
}
finally {
    if (Test-Path -LiteralPath $dependencyCacheRoot) {
        Remove-Item -LiteralPath $dependencyCacheRoot -Recurse -Force
    }
}

Write-Host "Launcher built at: $outExe"
