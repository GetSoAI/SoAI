$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
$script:SoAIInstallerPath = $PSCommandPath

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
    $localInstaller = 'install_soai_from_release.bat'
    if ([IO.File]::Exists((Join-Path $sourceRoot 'backend\core\bootstrap\filename_digests.json')) -and [IO.File]::Exists((Join-Path $sourceRoot 'install-soai-from-release.bat'))) {
        $localInstaller = 'install-soai-from-release.bat'
    }
    $requiredFiles = @(
        'VERSION',
        'backend\main.py',
        'frontend\index.html',
        'plugins\ollama.soaiplugin',
        $localInstaller,
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

function Get-SoAIHttpRetryDecision {
    param(
        [Parameter(Mandatory=$true)][Exception]$Failure,
        [Parameter(Mandatory=$true)][int]$Attempt
    )
    $httpStatus = 0
    $networkStatus = ''
    $retryAfter = ''
    $retryable = $false
    $integrityFailure = $false
    $visited = New-Object 'System.Collections.Generic.HashSet[Exception]'
    for ($current = $Failure; $null -ne $current -and $visited.Add($current); $current = $current.InnerException) {
        if ($current -is [System.Security.Authentication.AuthenticationException]) {
            $retryable = $false
            $integrityFailure = $true
            break
        }
        if ($current -is [System.Net.WebException]) {
            $networkStatus = [string]$current.Status
            if ($current.Response -is [System.Net.HttpWebResponse]) {
                $httpStatus = [int]$current.Response.StatusCode
                $retryAfter = $current.Response.Headers['Retry-After']
            }
            $retryable = $networkStatus -in @(
                'Timeout', 'ConnectFailure', 'NameResolutionFailure', 'ProxyNameResolutionFailure',
                'ReceiveFailure', 'SendFailure', 'ConnectionClosed', 'KeepAliveFailure'
            )
            if ($networkStatus -in @('TrustFailure', 'SecureChannelFailure', 'RequestCanceled')) {
                $retryable = $false
                $integrityFailure = $true
                break
            }
        }
        elseif ($PSVersionTable.PSVersion.Major -ge 6 -and $current -is [Microsoft.PowerShell.Commands.HttpResponseException]) {
            $httpStatus = [int]$current.Response.StatusCode
            if ($null -ne $current.Response.Headers.RetryAfter) {
                $retryAfter = $current.Response.Headers.RetryAfter.ToString()
            }
        }
        elseif ($current -is [System.Net.Sockets.SocketException]) {
            $networkStatus = [string]$current.SocketErrorCode
            $retryable = $networkStatus -in @(
                'NetworkDown', 'NetworkUnreachable', 'ConnectionAborted', 'ConnectionReset',
                'HostDown', 'HostUnreachable', 'TimedOut', 'ConnectionRefused', 'HostNotFound',
                'TryAgain', 'NoData'
            )
        }
        elseif ($current -is [TimeoutException]) {
            $networkStatus = 'Timeout'
            $retryable = $true
        }
    }
    if ($httpStatus -ne 0 -and !$integrityFailure) {
        $retryable = $httpStatus -in @(408, 429, 500, 502, 503, 504)
    }
    $delay = -1.0
    if ($retryable -and $Attempt -lt 6) {
        $delay = [Math]::Min(30, [Math]::Pow(2, $Attempt))
        $seconds = 0.0
        $date = [DateTimeOffset]::MinValue
        if (![string]::IsNullOrWhiteSpace($retryAfter)) {
            if ([double]::TryParse($retryAfter, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$seconds)) {
                if ([double]::IsNaN($seconds) -or $seconds -lt 0) {
                    $seconds = 0
                }
            }
            elseif ([DateTimeOffset]::TryParse($retryAfter, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AssumeUniversal, [ref]$date)) {
                $seconds = [Math]::Max(0, ($date - [DateTimeOffset]::UtcNow).TotalSeconds)
            }
            if ($seconds -gt 300) {
                $delay = -1
            }
            else {
                $delay = [Math]::Max($delay, $seconds)
            }
        }
    }
    return [pscustomobject]@{
        DelaySeconds = $delay
        HttpStatus = $httpStatus
        NetworkStatus = $networkStatus
        ExceptionType = $Failure.GetType().FullName
    }
}

function Invoke-SoAIHttpDownload {
    param(
        [Parameter(Mandatory=$true)][uri]$Uri,
        [Parameter(Mandatory=$true)][string]$Destination,
        [Parameter(Mandatory=$true)][int]$TimeoutSeconds,
        [Parameter(Mandatory=$true)][string]$DiagnosticDirectory,
        [hashtable]$Headers = @{}
    )
    if ($Uri.Scheme -ne 'https') {
        throw 'SoAI downloads require HTTPS.'
    }
    New-Item -ItemType Directory -Force -Path $DiagnosticDirectory | Out-Null
    $operation = [Guid]::NewGuid().ToString('N')
    $safeUri = [UriBuilder]::new($Uri)
    $safeUri.UserName = ''
    $safeUri.Password = ''
    $safeUri.Query = ''
    $safeUri.Fragment = ''
    for ($attempt = 1; $attempt -le 6; $attempt += 1) {
        $evidencePath = Join-Path $DiagnosticDirectory "download-$operation.attempt-$attempt.json"
        $evidence = [ordered]@{
            command = 'Invoke-WebRequest'
            uri = $safeUri.Uri.AbsoluteUri
            attempt = $attempt
            timeout_seconds = $TimeoutSeconds
            started_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
            outcome = 'started'
        }
        $evidence | ConvertTo-Json | Set-Content -LiteralPath $evidencePath -Encoding UTF8 -ErrorAction Stop
        if (Test-Path -LiteralPath $Destination) {
            Remove-Item -LiteralPath $Destination -Force -ErrorAction Stop
        }
        try {
            Invoke-WebRequest -Uri $Uri -OutFile $Destination -Headers $Headers -UseBasicParsing `
                -MaximumRedirection 20 -TimeoutSec $TimeoutSeconds -ErrorAction Stop
        }
        catch {
            $decision = Get-SoAIHttpRetryDecision -Failure $_.Exception -Attempt $attempt
            $evidence['outcome'] = 'failed'
            $evidence['http_status'] = $decision.HttpStatus
            $evidence['network_status'] = $decision.NetworkStatus
            $evidence['exception_type'] = $decision.ExceptionType
            $evidence['retry_delay_seconds'] = $decision.DelaySeconds
            $evidence | ConvertTo-Json | Set-Content -LiteralPath $evidencePath -Encoding UTF8 -ErrorAction Stop
            Write-Warning "Download attempt $attempt/6 failed. Diagnostics: $evidencePath"
            if ($decision.DelaySeconds -lt 0) {
                throw
            }
            Start-Sleep -Milliseconds ([int][Math]::Ceiling($decision.DelaySeconds * 1000))
            continue
        }
        $evidence['outcome'] = 'downloaded'
        $evidence | ConvertTo-Json | Set-Content -LiteralPath $evidencePath -Encoding UTF8 -ErrorAction Stop
        return
    }
}

function Save-SoAIReleaseAsset {
    param(
        [Parameter(Mandatory = $true)][object]$Asset,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$DiagnosticDirectory
    )
    Invoke-SoAIHttpDownload -Uri $Asset.Url -Destination $Destination -TimeoutSeconds 7200 -DiagnosticDirectory $DiagnosticDirectory
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
    $diagnosticDirectory = Join-Path ([IO.Path]::GetTempPath()) ("soai-install-diagnostics-" + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $diagnosticDirectory | Out-Null
    Write-SoAIStatus "Installer diagnostics: $diagnosticDirectory"
    $releasePath = Join-Path $diagnosticDirectory 'release.json'
    Invoke-SoAIHttpDownload -Uri 'https://api.github.com/repos/GetSoAI/SoAI/releases/latest' `
        -Headers $headers -Destination $releasePath -TimeoutSeconds 120 -DiagnosticDirectory $diagnosticDirectory
    if ((Get-Item -LiteralPath $releasePath).Length -gt 8388608) {
        throw 'Latest GitHub release metadata exceeds its size limit.'
    }
    $release = [IO.File]::ReadAllText($releasePath) | ConvertFrom-Json
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
        Save-SoAIReleaseAsset -Asset $checksumAsset -Destination $checksumPath -DiagnosticDirectory $diagnosticDirectory
        Save-SoAIReleaseAsset -Asset $setupAsset -Destination $setupPath -DiagnosticDirectory $diagnosticDirectory
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
        Write-SoAIStatus 'Starting the checksum-verified SoAI Windows installer...'
        $process = Start-Process -FilePath $setupPath -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            throw "SoAI Windows installer failed with exit code $($process.ExitCode)."
        }
        $installSucceeded = $true
    } catch {
        Write-Warning "Installer diagnostics: $diagnosticDirectory"
        throw
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
