$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
$script:SoAIInstallerPath = $MyInvocation.MyCommand.Path

function Write-SoAIStatus {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host ">>> $Message"
}

function Get-SoAILocalPayloadRoot {
    $scriptPath = $script:SoAIInstallerPath
    if ([string]::IsNullOrWhiteSpace($scriptPath)) {
        return $null
    }
    $scriptItem = Get-Item -LiteralPath $scriptPath -ErrorAction SilentlyContinue
    if ($null -eq $scriptItem -or $scriptItem.PSIsContainer) {
        return $null
    }
    $sourceRoot = $scriptItem.Directory.FullName
    $requiredFiles = @(
        'VERSION',
        'backend\main.py',
        'frontend\index.html',
        'plugins\ollama.soaiplugin',
        'install-soai-from-release.bat',
        'soai.exe'
    )
    foreach ($relativePath in $requiredFiles) {
        $candidate = Join-Path $sourceRoot $relativePath
        if (!(Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return $null
        }
    }
    return $sourceRoot
}

function Test-SoAIAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-SoAILocalInstall {
    param([Parameter(Mandatory = $true)][string]$SourceRoot)
    $launcherPath = Join-Path $SourceRoot 'soai.exe'
    Write-SoAIStatus 'Complete local SoAI payload detected; release download will be skipped.'
    if (Test-SoAIAdministrator) {
        & $launcherPath install
        if ($LASTEXITCODE -ne 0) {
            throw "Local SoAI installer failed with exit code $LASTEXITCODE."
        }
        return
    }
    Write-SoAIStatus 'Administrator privileges are required to install SoAI.'
    $process = Start-Process -FilePath $launcherPath -ArgumentList 'install' -Verb RunAs -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Elevated local SoAI installer failed with exit code $($process.ExitCode)."
    }
}

function Get-SoAIReleaseAsset {
    param(
        [Parameter(Mandatory = $true)][object[]]$Assets,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Tag,
        [Parameter(Mandatory = $true)][long]$MaximumBytes
    )
    $matches = @($Assets | Where-Object { $_.name -eq $Name })
    if ($matches.Count -ne 1) {
        throw "Latest GitHub release must contain exactly one asset named $Name."
    }
    $asset = $matches[0]
    $expectedUrl = "https://github.com/GetSoAI/SoAI/releases/download/$Tag/$Name"
    if ($asset.browser_download_url -ne $expectedUrl) {
        throw "Latest GitHub release asset URL is invalid: $Name"
    }
    $size = 0L
    if (![long]::TryParse([string]$asset.size, [ref]$size) -or $size -le 0 -or $size -gt $MaximumBytes) {
        throw "Latest GitHub release asset size is invalid: $Name"
    }
    return [pscustomobject]@{
        Name = $Name
        Size = $size
        Url = $expectedUrl
    }
}

function Save-SoAIReleaseAsset {
    param(
        [Parameter(Mandatory = $true)][object]$Asset,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    Invoke-WebRequest -Uri $Asset.Url -OutFile $Destination -UseBasicParsing -TimeoutSec 7200
    $download = Get-Item -LiteralPath $Destination
    if ($download.Length -ne $Asset.Size) {
        throw "Downloaded release asset size is invalid: $($Asset.Name)"
    }
}

function Invoke-SoAINetworkInstall {
    [Net.ServicePointManager]::SecurityProtocol = `
        [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Write-SoAIStatus 'Resolving the latest published SoAI release from GitHub...'
    $headers = @{
        Accept = 'application/vnd.github+json'
        'User-Agent' = 'SoAI-Installer/1'
        'X-GitHub-Api-Version' = '2022-11-28'
    }
    $release = Invoke-RestMethod `
        -Uri 'https://api.github.com/repos/GetSoAI/SoAI/releases/latest' `
        -Headers $headers `
        -UseBasicParsing `
        -TimeoutSec 120
    if ($release.draft -ne $false -or $release.prerelease -ne $false) {
        throw 'Latest GitHub release is not a published stable release.'
    }
    $tag = [string]$release.tag_name
    if ($tag -notmatch '^v[0-9]+\.[0-9]+\.[0-9]+$') {
        throw 'Latest GitHub release tag is invalid.'
    }
    $version = $tag.Substring(1)
    $setupName = "SoAI-$version-windows-x64-setup.exe"
    $checksumName = "$setupName.sha256"
    $assets = @($release.assets)
    $setupAsset = Get-SoAIReleaseAsset `
        -Assets $assets `
        -Name $setupName `
        -Tag $tag `
        -MaximumBytes 2147483648
    $checksumAsset = Get-SoAIReleaseAsset `
        -Assets $assets `
        -Name $checksumName `
        -Tag $tag `
        -MaximumBytes 1024
    $temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ("soai-install-" + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
    $installSucceeded = $false
    try {
        $setupPath = Join-Path $temporaryRoot $setupName
        $checksumPath = Join-Path $temporaryRoot $checksumName
        Write-SoAIStatus "Downloading SoAI $version for Windows..."
        Save-SoAIReleaseAsset -Asset $checksumAsset -Destination $checksumPath
        Save-SoAIReleaseAsset -Asset $setupAsset -Destination $setupPath
        $checksumText = [IO.File]::ReadAllText($checksumPath)
        $escapedSetupName = [Regex]::Escape($setupName)
        if ($checksumText -notmatch "^([0-9a-f]{64})  $escapedSetupName`r?`n?$") {
            throw 'SoAI Windows installer checksum sidecar is invalid.'
        }
        $expectedHash = $Matches[1]
        $actualHash = (Get-FileHash -LiteralPath $setupPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            throw 'SoAI Windows installer checksum verification failed.'
        }
        Write-SoAIStatus 'Starting the verified SoAI Windows installer...'
        $process = Start-Process -FilePath $setupPath -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            throw "SoAI Windows installer failed with exit code $($process.ExitCode)."
        }
        $installSucceeded = $true
    } finally {
        if (Test-Path -LiteralPath $temporaryRoot) {
            try {
                Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
            } catch {
                if ($installSucceeded) {
                    throw
                }
                Write-Warning "Failed to remove temporary installer directory: $temporaryRoot"
            }
        }
    }
}

if ($env:OS -ne 'Windows_NT') {
    throw 'This installer supports Windows only.'
}
if (![Environment]::Is64BitOperatingSystem -or [Environment]::OSVersion.Version.Major -lt 10) {
    throw 'SoAI requires 64-bit Windows 10 or later.'
}
$localPayloadRoot = Get-SoAILocalPayloadRoot
if ($null -ne $localPayloadRoot) {
    Invoke-SoAILocalInstall -SourceRoot $localPayloadRoot
    Write-SoAIStatus 'Local SoAI installation completed successfully.'
} else {
    Invoke-SoAINetworkInstall
    Write-SoAIStatus 'SoAI installation completed successfully.'
}
