[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InstallRoot,
    [string]$PythonVersion = '3.13.14',
    [string]$PythonUrl = 'https://www.nuget.org/api/v2/package/python/3.13.14',
    [string]$PythonSha256 = '9AC15CFA6CAB1115C83D48F2AF55C554EFA4D1BB044BBC4AB1C9D17AD426E16C',
    [string]$WebView2BootstrapperUrl = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703',
    [string]$VisualCppRedistUrl = 'https://aka.ms/vs/17/release/vc_redist.x64.exe',
    [string]$VisualCppAppLocalUrl = 'https://www.nuget.org/api/v2/package/VCLibs.VCRuntime.140/1.0.4',
    [string]$VisualCppAppLocalSha256 = 'EA8FAD02D8DE9CA1AB4E1D20C282166B3386ADF91A9B143019D59507229EA375',
    [string]$StatusPath,
    [int]$DependencyInstallTimeoutSeconds = 7200,
    [switch]$BootstrapOnly
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$script:InstallProgress = 35
$script:InstallStatusMessage = ''
$script:InstallerDownloadRoot = Join-Path $env:TEMP (
    "SoAI-Installer-" + [Guid]::NewGuid().ToString('N')
)
$script:ReleasedInstallerDownloadRoot = Join-Path $env:TEMP 'SoAI-Installer'

function Write-Step {
    param([Parameter(Mandatory=$true)][string]$Message)
    Write-Host "[SoAI] $Message"
    Write-InstallStatus -Message $Message
}

function Set-InstallProgress {
    param(
        [Parameter(Mandatory=$true)][int]$Progress,
        [string]$Message
    )
    $script:InstallProgress = [Math]::Max(35, [Math]::Min(95, $Progress))
    if (![string]::IsNullOrWhiteSpace($Message)) {
        Write-Step $Message
    }
    else {
        Write-InstallStatus
    }
}

function Write-InstallStatus {
    param([string]$Message)
    if ([string]::IsNullOrWhiteSpace($StatusPath)) {
        return
    }
    try {
        $statusDir = Split-Path -Parent $StatusPath
        New-Item -ItemType Directory -Force -Path $statusDir | Out-Null
        if (![string]::IsNullOrWhiteSpace($Message)) {
            $script:InstallStatusMessage = $Message.Replace("`r", ' ').Replace("`n", ' ').Trim()
        }
        $tempPath = "$StatusPath.tmp"
        @(
            '[status]'
            "progress=$script:InstallProgress"
            "message=$script:InstallStatusMessage"
            "updated_at_utc=$([DateTime]::UtcNow.ToString('o'))"
        ) | Set-Content -LiteralPath $tempPath -Encoding ASCII
        Move-Item -LiteralPath $tempPath -Destination $StatusPath -Force
    }
    catch {
    }
}

function Format-SoAILogLine {
    param([Parameter(Mandatory=$true)][string]$Line)
    $trimmed = $Line.Trim()
    $match = [regex]::Match(
        $trimmed,
        '^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}| UTC)?\s+-\s+\[[^\]]+\]\s+-\s+(TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\s+-\s+(.*)$'
    )
    if ($match.Success) {
        return $match.Groups[2].Value.Trim()
    }
    return $trimmed
}

function Get-UsefulLogTailMessage {
    param([Parameter(Mandatory=$true)][string]$LogPath)
    if (!(Test-Path -LiteralPath $LogPath)) {
        return ''
    }
    $lines = @(Get-Content -LiteralPath $LogPath -Tail 80 -ErrorAction SilentlyContinue)
    for ($index = $lines.Count - 1; $index -ge 0; $index -= 1) {
        $line = $lines[$index]
        if ($line -eq $null) {
            continue
        }
        $formatted = Format-SoAILogLine $line.ToString()
        if ([string]::IsNullOrWhiteSpace($formatted)) {
            continue
        }
        if ($formatted -match '^Traceback\b' -or $formatted -match '^\s*File\s+"') {
            continue
        }
        $exceptionMatch = [regex]::Match($formatted, '^[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception):\s*(.+)$')
        if ($exceptionMatch.Success) {
            return $exceptionMatch.Groups[1].Value.Trim()
        }
        return $formatted.Trim()
    }
    return ''
}

function Remove-ConsoleDecorations {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return ''
    }
    return ($Value -replace "`e\[[0-9;?]*[ -/]*[@-~]", '').Trim()
}

function Get-HeartbeatLogMessage {
    param([Parameter(Mandatory=$true)][string]$LogPath)
    if (!(Test-Path -LiteralPath $LogPath)) {
        return ''
    }
    try {
        $lines = @(Get-Content -LiteralPath $LogPath -Tail 20 -ErrorAction Stop)
    }
    catch {
        return ''
    }
    for ($index = $lines.Count - 1; $index -ge 0; $index -= 1) {
        $line = Format-SoAILogLine (Remove-ConsoleDecorations $lines[$index])
        $toolLineMatch = [regex]::Match($line, '\b((?:pip|playwright):\s+.+)$')
        if ($toolLineMatch.Success) {
            $line = $toolLineMatch.Groups[1].Value.Trim()
        }
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        if ($line -match '^\d{4}-\d{2}-\d{2}(?:[T ].*)?$') {
            continue
        }
        if ($line -match '^\d{2}:\d{2}(?::\d{0,2}(?:\.\d*)?(?:Z|[+-]\d{0,2}:?\d{0,2})?)?$') {
            continue
        }
        if ($line -match '^\s*-?\s*\[[^\]]+\]\s*-\s*(?:TRACE|DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL)\s*-?\s*$') {
            continue
        }
        if ($line -match '\[SoAI/') {
            continue
        }
        $playwrightProgressMatch = [regex]::Match($line, '^playwright:\s+\|.*\|\s+(\d{1,3})%\s+of\s+(.+)$')
        if ($playwrightProgressMatch.Success) {
            return "Playwright: downloading browser components ($($playwrightProgressMatch.Groups[1].Value)% of $($playwrightProgressMatch.Groups[2].Value.Trim()))"
        }
        if ($line -match '^playwright:\s+\|') {
            return 'Playwright: downloading browser components'
        }
        $playwrightDownloadMatch = [regex]::Match($line, '^playwright:\s+Downloading\s+(.+?)\s+from\s+https?://')
        if ($playwrightDownloadMatch.Success) {
            return "Playwright: downloading $($playwrightDownloadMatch.Groups[1].Value.Trim())"
        }
        if ($line -match '[■█]{4,}') {
            if ($line -match '^\s*playwright:') {
                return 'playwright: downloading browser components'
            }
            continue
        }
        if ($line -match '^\[notice\]') {
            continue
        }
        if ($line -match '^\s*(\||/|-|\\)+\s*$') {
            continue
        }
        if ($line.Length -gt 120) {
            $line = $line.Substring(0, 117) + '...'
        }
        return $line
    }
    return ''
}

function Format-CommandHeartbeatMessage {
    param(
        [Parameter(Mandatory=$true)][string]$BaseMessage,
        [Parameter(Mandatory=$true)][DateTime]$StartedUtc,
        [Parameter(Mandatory=$true)][string]$StdoutLogPath,
        [Parameter(Mandatory=$true)][string]$StderrLogPath
    )
    $elapsed = [DateTime]::UtcNow - $StartedUtc
    $message = "$BaseMessage (elapsed {0:mm\:ss})" -f $elapsed
    $detail = Get-HeartbeatLogMessage -LogPath $StderrLogPath
    if ([string]::IsNullOrWhiteSpace($detail)) {
        $detail = Get-HeartbeatLogMessage -LogPath $StdoutLogPath
    }
    if (![string]::IsNullOrWhiteSpace($detail)) {
        $message = "$message - $detail"
    }
    return $message
}

function Get-InstallLogDir {
    param([Parameter(Mandatory=$true)][string]$Root)
    $logDir = Resolve-ChildPath -Root $Root -Child 'installer-support\logs'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    return $logDir
}

function Write-LoggedCommandTail {
    param(
        [Parameter(Mandatory=$true)][string]$LogPath,
        [int]$LineCount = 30
    )
    if (!(Test-Path -LiteralPath $LogPath)) {
        return
    }
    Write-Step "Last lines from $(Split-Path -Leaf $LogPath):"
    Get-Content -LiteralPath $LogPath -Tail $LineCount -ErrorAction SilentlyContinue |
        ForEach-Object {
            if ($_ -ne $null -and $_.ToString().Trim().Length -gt 0) {
                Write-Host (Format-SoAILogLine $_.ToString())
            }
        }
}

function Get-ProgressFingerprint {
    param([Parameter(Mandatory=$true)][string[]]$Paths)
    $parts = New-Object System.Collections.Generic.List[string]
    foreach ($path in $Paths) {
        if ([string]::IsNullOrWhiteSpace($path)) {
            continue
        }
        $item = Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        if (!$item) {
            [void]$parts.Add("$path|missing")
            continue
        }
        if ($item.PSIsContainer) {
            $files = @(Get-ChildItem -LiteralPath $item.FullName -Recurse -File -Force -ErrorAction SilentlyContinue |
                Sort-Object FullName)
            if ($files.Count -eq 0) {
                [void]$parts.Add("$path|dir|empty|$($item.LastWriteTimeUtc.Ticks)")
                continue
            }
            [void]$parts.Add("$path|dir")
        }
        else {
            $files = @($item)
        }
        foreach ($file in $files) {
            try {
                $stream = [IO.File]::Open($file.FullName, [IO.FileMode]::Open, [IO.FileAccess]::Read, ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
                try { $length = $stream.Length }
                finally { $stream.Dispose() }
            }
            catch [IO.FileNotFoundException], [IO.DirectoryNotFoundException] {
                [void]$parts.Add("$($file.FullName)|missing")
                continue
            }
            catch [UnauthorizedAccessException] {
                [void]$parts.Add("$($file.FullName)|unavailable|access")
                continue
            }
            catch [IO.IOException] {
                if (($_.Exception.GetBaseException().HResult -band 0xFFFF) -notin @(32, 33)) { throw }
                [void]$parts.Add("$($file.FullName)|unavailable|sharing")
                continue
            }
            $file.Refresh()
            if (!$file.Exists) {
                [void]$parts.Add("$($file.FullName)|missing")
                continue
            }
            [void]$parts.Add("$($file.FullName)|file|$length|$($file.LastWriteTimeUtc.Ticks)")
        }
    }
    return ($parts -join "`n")
}

function Stop-ProcessTree {
    param([Parameter(Mandatory=$true)][int]$ProcessId)
    & "$env:WINDIR\System32\taskkill.exe" /PID $ProcessId /T /F | Out-Null
}

function Quote-ProcessArgument {
    param([AllowNull()][string]$Value)
    if ($null -eq $Value) {
        return '""'
    }
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') {
        return $Value
    }
    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $backslashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq [char]'\') {
            $backslashes += 1
            continue
        }
        if ($character -eq [char]'"') {
            if ($backslashes -gt 0) {
                [void]$builder.Append([char]'\', $backslashes * 2)
                $backslashes = 0
            }
            [void]$builder.Append([char]'\')
            [void]$builder.Append([char]'"')
            continue
        }
        if ($backslashes -gt 0) {
            [void]$builder.Append([char]'\', $backslashes)
            $backslashes = 0
        }
        [void]$builder.Append($character)
    }
    if ($backslashes -gt 0) {
        [void]$builder.Append([char]'\', $backslashes * 2)
    }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Join-ProcessArguments {
    param([Parameter(Mandatory=$true)][string[]]$Arguments)
    $quoted = @()
    foreach ($argument in $Arguments) {
        $quoted += Quote-ProcessArgument $argument
    }
    return $quoted -join ' '
}

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$PhaseName,
        [Parameter(Mandatory=$true)][string]$WorkingDirectory,
        [Parameter(Mandatory=$true)][string]$Executable,
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [Parameter(Mandatory=$true)][hashtable]$EnvironmentValues,
        [int]$TimeoutSeconds = 7200,
        [string[]]$ProgressPaths = @(),
        [int]$NoProgressTimeoutSeconds = 0,
        [int]$HeartbeatSeconds = 0,
        [string]$HeartbeatMessage,
        [int]$ProgressStart = 0,
        [int]$ProgressEnd = 0
    )
    $logDir = Get-InstallLogDir -Root $Root
    $safePhase = $PhaseName -replace '[^A-Za-z0-9_.-]', '-'
    $stdoutLogPath = Join-Path $logDir "$safePhase.out.log"
    $stderrLogPath = Join-Path $logDir "$safePhase.err.log"
    Remove-Item -LiteralPath $stdoutLogPath, $stderrLogPath -Force -ErrorAction SilentlyContinue
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Executable
    $psi.Arguments = Join-ProcessArguments $Arguments
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    foreach ($name in $EnvironmentValues.Keys) {
        $psi.EnvironmentVariables[$name] = [string]$EnvironmentValues[$name]
    }
    $stdoutStream = [System.IO.File]::Open($stdoutLogPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::ReadWrite)
    $stderrStream = [System.IO.File]::Open($stderrLogPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::ReadWrite)
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    $stdoutTask = $null
    $stderrTask = $null
    $exitCode = $null
    $script:LastFailedInstallPhase = $null
    if ($ProgressStart -gt 0) {
        Set-InstallProgress -Progress $ProgressStart -Message $HeartbeatMessage
    }
    try {
        [void]$process.Start()
        $stdoutTask = $process.StandardOutput.BaseStream.CopyToAsync($stdoutStream)
        $stderrTask = $process.StandardError.BaseStream.CopyToAsync($stderrStream)
        $deadlineUtc = [DateTime]::UtcNow.AddSeconds([Math]::Max(60, $TimeoutSeconds))
        $progressDeadlineEnabled = $NoProgressTimeoutSeconds -gt 0
        $progressWatchPaths = @($stdoutLogPath, $stderrLogPath) + @($ProgressPaths)
        $lastProgressFingerprint = Get-ProgressFingerprint -Paths $progressWatchPaths
        $lastProgressUtc = [DateTime]::UtcNow
        $startedUtc = [DateTime]::UtcNow
        $nextHeartbeatUtc = $startedUtc.AddSeconds([Math]::Max(30, $HeartbeatSeconds))
        while (!$process.WaitForExit(5000)) {
            $nowUtc = [DateTime]::UtcNow
            if ($HeartbeatSeconds -gt 0 -and $nowUtc -ge $nextHeartbeatUtc) {
                if ($ProgressStart -gt 0 -and $ProgressEnd -gt $ProgressStart) {
                    $expectedSeconds = [Math]::Min([Math]::Max(900, $TimeoutSeconds / 4), 1800)
                    $fraction = [Math]::Min(0.95, [Math]::Max(0.0, ($nowUtc - $startedUtc).TotalSeconds / $expectedSeconds))
                    $currentProgress = $ProgressStart + [int][Math]::Floor(($ProgressEnd - $ProgressStart - 1) * $fraction)
                    $heartbeat = Format-CommandHeartbeatMessage -BaseMessage $HeartbeatMessage -StartedUtc $startedUtc -StdoutLogPath $stdoutLogPath -StderrLogPath $stderrLogPath
                    Set-InstallProgress -Progress $currentProgress -Message $heartbeat
                }
                else {
                    $heartbeat = Format-CommandHeartbeatMessage -BaseMessage $HeartbeatMessage -StartedUtc $startedUtc -StdoutLogPath $stdoutLogPath -StderrLogPath $stderrLogPath
                    Write-InstallStatus -Message $heartbeat
                }
                $nextHeartbeatUtc = $nowUtc.AddSeconds($HeartbeatSeconds)
            }
            if ($nowUtc -gt $deadlineUtc) {
                try {
                    Stop-ProcessTree -ProcessId $process.Id
                }
                catch {
                }
                if ($stdoutTask -and $stderrTask) {
                    [void][System.Threading.Tasks.Task]::WaitAll(@($stdoutTask, $stderrTask), 30000)
                }
                Write-LoggedCommandTail -LogPath $stdoutLogPath
                Write-LoggedCommandTail -LogPath $stderrLogPath
                $script:LastFailedInstallPhase = $PhaseName
                throw "SoAI $PhaseName did not finish within $TimeoutSeconds seconds."
            }
            if ($progressDeadlineEnabled) {
                $fingerprint = Get-ProgressFingerprint -Paths $progressWatchPaths
                if ($fingerprint -ne $lastProgressFingerprint) {
                    $lastProgressFingerprint = $fingerprint
                    $lastProgressUtc = $nowUtc
                }
                elseif (($nowUtc - $lastProgressUtc).TotalSeconds -ge $NoProgressTimeoutSeconds) {
                    try {
                        Stop-ProcessTree -ProcessId $process.Id
                    }
                    catch {
                    }
                    if ($stdoutTask -and $stderrTask) {
                        [void][System.Threading.Tasks.Task]::WaitAll(@($stdoutTask, $stderrTask), 30000)
                    }
                    Write-LoggedCommandTail -LogPath $stdoutLogPath
                    Write-LoggedCommandTail -LogPath $stderrLogPath
                    $script:LastFailedInstallPhase = $PhaseName
                    throw "SoAI $PhaseName made no observable progress for $NoProgressTimeoutSeconds seconds."
                }
            }
        }
        $process.WaitForExit()
        if ($stdoutTask -and $stderrTask) {
            [void][System.Threading.Tasks.Task]::WaitAll(@($stdoutTask, $stderrTask), 30000)
        }
        $exitCode = $process.ExitCode
    }
    finally {
        $process.Dispose()
        $stdoutStream.Dispose()
        $stderrStream.Dispose()
    }
    if ($exitCode -ne 0) {
        Write-LoggedCommandTail -LogPath $stdoutLogPath
        Write-LoggedCommandTail -LogPath $stderrLogPath
        $script:LastFailedInstallPhase = $PhaseName
        $usefulMessage = Get-UsefulLogTailMessage -LogPath $stderrLogPath
        if ([string]::IsNullOrWhiteSpace($usefulMessage)) {
            $usefulMessage = Get-UsefulLogTailMessage -LogPath $stdoutLogPath
        }
        if (![string]::IsNullOrWhiteSpace($usefulMessage)) {
            throw "SoAI $PhaseName failed: $usefulMessage"
        }
        throw "SoAI $PhaseName failed with exit code $exitCode. Logs: $stdoutLogPath and $stderrLogPath"
    }
    if ($ProgressEnd -gt 0) {
        Set-InstallProgress -Progress $ProgressEnd
    }
    $script:LastFailedInstallPhase = $null
    return $stdoutLogPath
}

function Resolve-FullPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $executionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
}

function Resolve-ChildPath {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$Child
    )
    $rootFull = Resolve-FullPath $Root
    $combined = Resolve-FullPath (Join-Path $rootFull $Child)
    $prefix = $rootFull.TrimEnd('\') + '\'
    if (!$combined.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Resolved path escapes the SoAI installation root: $combined"
    }
    return $combined
}

function Test-ExecutableHeader {
    param([Parameter(Mandatory=$true)][string]$Path)
    if (!(Test-Path -LiteralPath $Path)) {
        return $false
    }
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        if ($stream.Length -lt 2) {
            return $false
        }
        return $stream.ReadByte() -eq 0x4d -and $stream.ReadByte() -eq 0x5a
    }
    finally {
        $stream.Dispose()
    }
}

function Test-ZipHeader {
    param([Parameter(Mandatory=$true)][string]$Path)
    if (!(Test-Path -LiteralPath $Path)) {
        return $false
    }
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        if ($stream.Length -lt 2) {
            return $false
        }
        return $stream.ReadByte() -eq 0x50 -and $stream.ReadByte() -eq 0x4b
    }
    finally {
        $stream.Dispose()
    }
}

function Assert-AuthenticodeValid {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [string]$ExpectedPublisher
    )
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -ne 'Valid') {
        throw "Downloaded executable signature is not valid: $Path"
    }
    if ($ExpectedPublisher -and $signature.SignerCertificate.Subject -notlike "*$ExpectedPublisher*") {
        throw "Downloaded executable was not signed by the expected publisher: $ExpectedPublisher"
    }
}

function Assert-Hash {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [string]$Sha256
    )
    if ([string]::IsNullOrWhiteSpace($Sha256)) {
        return
    }
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    if (![string]::Equals($actual, $Sha256, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "SHA-256 mismatch for $Path. Expected $Sha256 but got $actual."
    }
}

function Join-PathEntries {
    param([Parameter(Mandatory=$true)][string[]]$Entries)
    $usableEntries = New-Object System.Collections.Generic.List[string]
    foreach ($entry in $Entries) {
        if (![string]::IsNullOrWhiteSpace($entry)) {
            [void]$usableEntries.Add($entry)
        }
    }
    return ($usableEntries.ToArray() -join [System.IO.Path]::PathSeparator)
}

function Get-SoAIProcessPath {
    param([Parameter(Mandatory=$true)][string]$Root)
    $rootFull = Resolve-FullPath $Root
    $pythonDir = Resolve-ChildPath -Root $Root -Child 'python'
    $venvScripts = Resolve-ChildPath -Root $Root -Child 'soai_main_venv\Scripts'
    $entries = New-Object System.Collections.Generic.List[string]
    foreach ($path in @($rootFull, $pythonDir, $venvScripts)) {
        if (Test-Path -LiteralPath $path -PathType Container) {
            [void]$entries.Add($path)
        }
    }
    if (![string]::IsNullOrWhiteSpace($env:PATH)) {
        [void]$entries.Add($env:PATH)
    }
    return Join-PathEntries -Entries $entries.ToArray()
}

function Download-File {
    param(
        [Parameter(Mandatory=$true)][string]$Uri,
        [Parameter(Mandatory=$true)][string]$Destination,
        [string]$Sha256,
        [ValidateSet('Exe','Zip')][string]$Kind = 'Exe'
    )
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    for ($attempt = 1; $attempt -le 3; $attempt += 1) {
        try {
            Write-Step "Downloading $Uri"
            $temp = "$Destination.download"
            Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue
            Invoke-WebRequest -Uri $Uri -OutFile $temp -UseBasicParsing -MaximumRedirection 20 -TimeoutSec 600
            if ($Kind -eq 'Exe' -and !(Test-ExecutableHeader $temp)) {
                throw 'download did not look like a Windows executable'
            }
            if ($Kind -eq 'Zip' -and !(Test-ZipHeader $temp)) {
                throw 'download did not look like a zip package'
            }
            Assert-Hash -Path $temp -Sha256 $Sha256
            Move-Item -LiteralPath $temp -Destination $Destination -Force
            return
        }
        catch {
            Remove-Item -LiteralPath "$Destination.download" -Force -ErrorAction SilentlyContinue
            if ($attempt -eq 3) {
                throw
            }
            Start-Sleep -Seconds (2 * $attempt)
        }
    }
}

function Get-VisualCppRuntimeVersion {
    $keys = @(
        'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64'
    )
    foreach ($key in $keys) {
        if (Test-Path -LiteralPath $key) {
            $value = Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue
            if ($value -and [int]$value.Installed -eq 1) {
                if (![string]::IsNullOrWhiteSpace($value.Version)) {
                    return $value.Version
                }
                return "14.$($value.Major).$($value.Minor).$($value.Bld)"
            }
        }
    }
    return $null
}

function Get-RequiredVisualCppRuntimeDllNames {
    return @(
        'msvcp140.dll',
        'msvcp140_1.dll',
        'msvcp140_2.dll',
        'msvcp140_atomic_wait.dll',
        'msvcp140_codecvt_ids.dll',
        'vcruntime140.dll',
        'vcruntime140_1.dll'
    )
}

function Get-SystemVisualCppRuntimeDllNames {
    return (Get-RequiredVisualCppRuntimeDllNames) + @('vcomp140.dll')
}

function Get-MissingVisualCppRuntimeFiles {
    param(
        [Parameter(Mandatory=$true)][string]$Directory,
        [Parameter(Mandatory=$true)][string[]]$DllNames
    )
    $missing = New-Object System.Collections.Generic.List[string]
    foreach ($dllName in $DllNames) {
        if (!(Test-Path -LiteralPath (Join-Path $Directory $dllName) -PathType Leaf)) {
            [void]$missing.Add($dllName)
        }
    }
    return $missing.ToArray()
}

function Install-VisualCppRuntime {
    param([Parameter(Mandatory=$true)][string]$Root)
    $version = Get-VisualCppRuntimeVersion
    $system32 = Join-Path $env:WINDIR 'System32'
    $missing = @(Get-MissingVisualCppRuntimeFiles -Directory $system32 -DllNames (Get-SystemVisualCppRuntimeDllNames))
    if ($version -and $missing.Count -eq 0) {
        Write-Step "Microsoft Visual C++ Runtime is already installed ($version)."
        Copy-AppLocalVisualCppRuntimeDlls -Root $Root
        return
    }

    $downloadDir = $script:InstallerDownloadRoot
    $redist = Join-Path $downloadDir 'vc_redist.x64.exe'
    Download-File -Uri $VisualCppRedistUrl -Destination $redist
    Assert-AuthenticodeValid -Path $redist -ExpectedPublisher 'Microsoft'

    Write-Step 'Installing Microsoft Visual C++ Runtime...'
    $process = Start-Process -FilePath $redist -ArgumentList @('/install', '/quiet', '/norestart') -PassThru
    if (!$process.WaitForExit(600000)) {
        try {
            $process.Kill()
        }
        catch {
        }
        throw 'Microsoft Visual C++ Runtime installer did not finish within 10 minutes.'
    }
    if ($process.ExitCode -ne 0 -and $process.ExitCode -ne 1638 -and $process.ExitCode -ne 3010) {
        throw "Microsoft Visual C++ Runtime installer failed with exit code $($process.ExitCode)."
    }
    $version = Get-VisualCppRuntimeVersion
    $missing = @(Get-MissingVisualCppRuntimeFiles -Directory $system32 -DllNames (Get-SystemVisualCppRuntimeDllNames))
    if ($missing.Count -eq 0) {
        Write-Step "Microsoft Visual C++ Runtime is ready ($version)."
    }
    else {
        Write-Step "Microsoft Visual C++ Runtime system install is still missing: $($missing -join ', '). SoAI will use app-local runtime DLLs where possible."
    }
    Copy-AppLocalVisualCppRuntimeDlls -Root $Root
}

function Copy-AppLocalVisualCppRuntimeDlls {
    param([Parameter(Mandatory=$true)][string]$Root)
    $dllNames = Get-RequiredVisualCppRuntimeDllNames
    $system32 = Join-Path $env:WINDIR 'System32'
    $systemMissing = @(Get-MissingVisualCppRuntimeFiles -Directory $system32 -DllNames $dllNames)
    $sourceDir = $system32
    if ($systemMissing.Count -ne 0) {
        $downloadDir = $script:InstallerDownloadRoot
        $package = Join-Path $downloadDir 'VCLibs.VCRuntime.140.1.0.4.nupkg'
        $packageZip = Join-Path $downloadDir 'VCLibs.VCRuntime.140.1.0.4.zip'
        $extractDir = Join-Path $downloadDir 'VCLibs.VCRuntime.140.1.0.4'
        if (!(Test-Path -LiteralPath $package)) {
            Download-File -Uri $VisualCppAppLocalUrl -Destination $package -Sha256 $VisualCppAppLocalSha256 -Kind Zip
        }
        else {
            Assert-Hash -Path $package -Sha256 $VisualCppAppLocalSha256
        }

        $sourceDir = Join-Path $extractDir 'runtimes\win-x64\native'
        if (!(Test-Path -LiteralPath $sourceDir -PathType Container)) {
            Remove-Item -LiteralPath $extractDir -Recurse -Force -ErrorAction SilentlyContinue
            Copy-Item -LiteralPath $package -Destination $packageZip -Force
            Expand-Archive -LiteralPath $packageZip -DestinationPath $extractDir -Force
        }
        if (!(Test-Path -LiteralPath $sourceDir -PathType Container)) {
            throw 'The app-local Visual C++ runtime package did not contain runtimes\win-x64\native.'
        }
    }

    $targets = New-Object System.Collections.Generic.List[string]
    [void]$targets.Add((Resolve-FullPath $Root))
    $pythonDir = Resolve-ChildPath -Root $Root -Child 'python'
    if (Test-Path -LiteralPath $pythonDir -PathType Container) {
        [void]$targets.Add($pythonDir)
    }
    $venvScripts = Resolve-ChildPath -Root $Root -Child 'soai_main_venv\Scripts'
    if (Test-Path -LiteralPath $venvScripts -PathType Container) {
        [void]$targets.Add($venvScripts)
    }

    foreach ($dllName in $dllNames) {
        $source = Join-Path $sourceDir $dllName
        if (!(Test-Path -LiteralPath $source -PathType Leaf)) {
            throw "The selected Visual C++ runtime source is missing $dllName."
        }
        foreach ($target in $targets) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $target $dllName) -Force
        }
    }
}

function Test-PythonRuntime {
    param([Parameter(Mandatory=$true)][string]$PythonExe)
    if (!(Test-Path -LiteralPath $PythonExe)) {
        return $false
    }
    try {
        $output = & $PythonExe --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            return $false
        }
        return ($output -join "`n") -like "Python $PythonVersion*"
    }
    catch {
        return $false
    }
}

function Copy-AppLocalPythonRuntimeDlls {
    param([Parameter(Mandatory=$true)][string]$Root)
    $pythonDir = Resolve-ChildPath -Root $Root -Child 'python'
    if (!(Test-Path -LiteralPath $pythonDir -PathType Container)) {
        return
    }

    $targets = New-Object System.Collections.Generic.List[string]
    [void]$targets.Add((Resolve-FullPath $Root))
    $venvScripts = Resolve-ChildPath -Root $Root -Child 'soai_main_venv\Scripts'
    if (Test-Path -LiteralPath $venvScripts -PathType Container) {
        [void]$targets.Add($venvScripts)
    }

    foreach ($dllName in @('vcruntime140.dll', 'vcruntime140_1.dll')) {
        $source = Join-Path $pythonDir $dllName
        if (!(Test-Path -LiteralPath $source -PathType Leaf)) {
            continue
        }
        foreach ($target in $targets) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $target $dllName) -Force
        }
    }
}

function Install-PythonRuntime {
    param([Parameter(Mandatory=$true)][string]$Root)
    $pythonDir = Resolve-ChildPath -Root $Root -Child 'python'
    $pythonExe = Join-Path $pythonDir 'python.exe'
    if (Test-PythonRuntime $pythonExe) {
        Write-Step "Python $PythonVersion runtime is already ready."
        Copy-AppLocalPythonRuntimeDlls -Root $Root
        return
    }

    if (Test-Path -LiteralPath $pythonDir) {
        Write-Step 'Removing incomplete Python runtime...'
        Remove-Item -LiteralPath $pythonDir -Recurse -Force
    }

    $downloadDir = $script:InstallerDownloadRoot
    $package = Join-Path $downloadDir "python-$PythonVersion.nupkg"
    $packageZip = Join-Path $downloadDir "python-$PythonVersion.zip"
    $extractDir = Join-Path $downloadDir "python-$PythonVersion-package"
    if (!(Test-Path -LiteralPath $package)) {
        Download-File -Uri $PythonUrl -Destination $package -Sha256 $PythonSha256 -Kind Zip
    }
    else {
        Assert-Hash -Path $package -Sha256 $PythonSha256
    }

    Write-Step "Extracting app-local Python $PythonVersion runtime..."
    Remove-Item -LiteralPath $extractDir -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item -LiteralPath $package -Destination $packageZip -Force
    Expand-Archive -LiteralPath $packageZip -DestinationPath $extractDir -Force
    $toolsDir = Join-Path $extractDir 'tools'
    if (!(Test-Path -LiteralPath (Join-Path $toolsDir 'python.exe'))) {
        throw 'The Python package did not contain tools\python.exe.'
    }
    Move-Item -LiteralPath $toolsDir -Destination $pythonDir -Force
    if (!(Test-PythonRuntime $pythonExe)) {
        throw 'The app-local Python runtime did not validate after extraction.'
    }
    Copy-AppLocalPythonRuntimeDlls -Root $Root
}

function Install-Stage0BootstrapDependencies {
    param([Parameter(Mandatory=$true)][string]$Root)
    $pythonExe = Resolve-ChildPath -Root $Root -Child 'python\python.exe'
    Write-Step 'Preparing the SoAI stage-0 bootstrap dependencies...'
    & $pythonExe -m pip install --disable-pip-version-check --no-warn-script-location --upgrade `
        'ruamel-yaml==0.19.1' `
        'httpx2==2.10.0' `
        'filelock==3.32.2' `
        'psutil==7.2.2'
    if ($LASTEXITCODE -ne 0) {
        throw "Stage-0 bootstrap dependency installation failed with exit code $LASTEXITCODE."
    }
}

function Get-WebView2RuntimeVersion {
    $appId = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
    $keys = @(
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\$appId",
        "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$appId",
        "HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$appId"
    )
    foreach ($key in $keys) {
        if (Test-Path -LiteralPath $key) {
            $value = (Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue).pv
            if (![string]::IsNullOrWhiteSpace($value) -and $value -ne '0.0.0.0') {
                return $value
            }
        }
    }
    return $null
}

function Install-WebView2Runtime {
    $version = Get-WebView2RuntimeVersion
    if ($version) {
        Write-Step "Microsoft Edge WebView2 Runtime is already installed ($version)."
        return
    }

    $downloadDir = $script:InstallerDownloadRoot
    $bootstrapper = Join-Path $downloadDir 'MicrosoftEdgeWebView2Setup.exe'
    if (!(Test-Path -LiteralPath $bootstrapper)) {
        Download-File -Uri $WebView2BootstrapperUrl -Destination $bootstrapper
    }
    Assert-AuthenticodeValid -Path $bootstrapper -ExpectedPublisher 'Microsoft'

    Write-Step 'Installing Microsoft Edge WebView2 Runtime...'
    $process = Start-Process -FilePath $bootstrapper -ArgumentList @('/silent', '/install') -PassThru
    if (!$process.WaitForExit(600000)) {
        try {
            $process.Kill()
        }
        catch {
        }
        throw 'WebView2 Runtime installer did not finish within 10 minutes.'
    }
    if ($process.ExitCode -ne 0) {
        throw "WebView2 Runtime installer failed with exit code $($process.ExitCode)."
    }
    $version = Get-WebView2RuntimeVersion
    if (!$version) {
        throw 'Microsoft Edge WebView2 Runtime was not detected after installation.'
    }
}

function New-TemporaryInstallDrive {
    param([Parameter(Mandatory=$true)][string]$Root)
    $resolvedRoot = Resolve-FullPath $Root
    foreach ($code in ([int][char]'Z')..([int][char]'P')) {
        $letter = [char]$code
        $drive = "$letter`:"
        $driveRoot = "$drive\"
        if (Test-Path -LiteralPath $driveRoot -ErrorAction SilentlyContinue) {
            continue
        }
        $result = & "$env:ComSpec" /c "subst $drive `"$resolvedRoot`""
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $driveRoot)) {
            return @{
                Drive = $drive
                Root = $driveRoot
            }
        }
    }
    throw 'No free drive letter was available for short-path dependency preparation.'
}

function Remove-TemporaryInstallDrive {
    param([Parameter(Mandatory=$true)][string]$Drive)
    & "$env:ComSpec" /c "subst $Drive /D" | Out-Null
}

function Remove-DirectoryTree {
    param([Parameter(Mandatory=$true)][string]$Path)
    if (!(Test-Path -LiteralPath $Path -PathType Container)) {
        return
    }
    try {
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
        return
    }
    catch {
    }

    $emptyRoot = Join-Path $env:TEMP ("SoAI-Empty-" + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $emptyRoot | Out-Null
    try {
        & "$env:WINDIR\System32\robocopy.exe" $emptyRoot $Path /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue
    }
    finally {
        Remove-Item -LiteralPath $emptyRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $Path -PathType Container) {
        throw "Failed to remove directory tree: $Path"
    }
}

function Remove-IncompleteManagedVenv {
    param([Parameter(Mandatory=$true)][string]$Root)
    $venvDir = Resolve-ChildPath -Root $Root -Child 'soai_main_venv'
    $venvPython = Join-Path $venvDir 'Scripts\python.exe'
    if ((Test-Path -LiteralPath $venvDir) -and !(Test-Path -LiteralPath $venvPython)) {
        Write-Step 'Removing incomplete SoAI managed Python environment...'
        Remove-DirectoryTree -Path $venvDir
    }
}

function Remove-LocalPackageBuildArtifacts {
    param([Parameter(Mandatory=$true)][string]$Root)
    $tikaRoot = Resolve-ChildPath -Root $Root -Child 'data\vendor\tika'
    if (!(Test-Path -LiteralPath $tikaRoot -PathType Container)) {
        return
    }
    foreach ($relative in @('build', 'dist')) {
        $path = Join-Path $tikaRoot $relative
        if (Test-Path -LiteralPath $path -PathType Container) {
            Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    Get-ChildItem -LiteralPath $tikaRoot -Directory -Force -Filter '*.egg-info' -ErrorAction SilentlyContinue |
        ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
}

function Write-PythonPhaseScripts {
    param([Parameter(Mandatory=$true)][string]$Root)
    $logDir = Get-InstallLogDir -Root $Root
    $createVenvScript = Join-Path $logDir 'create-managed-venv.py'
    $installDepsScript = Join-Path $logDir 'install-python-deps.py'
    $installArtifactsScript = Join-Path $logDir 'install-runtime-artifacts.py'

    Set-Content -LiteralPath $createVenvScript -Encoding UTF8 -Value @'
import os
import sys

repo_root = os.path.abspath(sys.argv[1])
sys.path.insert(0, os.path.join(repo_root, "backend"))
from core.bootstrap.windows_managed_venv import ensure_windows_managed_venv

print(ensure_windows_managed_venv(repo_root))
'@

    Set-Content -LiteralPath $installDepsScript -Encoding UTF8 -Value @'
import os
import sys

repo_root = os.path.abspath(sys.argv[1])
sys.path.insert(0, os.path.join(repo_root, "backend"))
from core.bootstrap.python_dependencies import bootstrap_python_dependencies_if_needed

changed = bootstrap_python_dependencies_if_needed(
    repo_root,
    python_executable=sys.executable,
)
print(f"python_dependencies_changed={changed}")
'@

    Set-Content -LiteralPath $installArtifactsScript -Encoding UTF8 -Value @'
import os
import sys

repo_root = os.path.abspath(sys.argv[1])
sys.path.insert(0, os.path.join(repo_root, "backend"))
from core.bootstrap.runtime_artifacts import ensure_runtime_artifacts_if_needed

ensure_runtime_artifacts_if_needed(
    repo_root,
    python_executable=sys.executable,
)
print("runtime_artifacts_ready=True")
'@

    return @{
        CreateVenv = $createVenvScript
        InstallDeps = $installDepsScript
        InstallArtifacts = $installArtifactsScript
    }
}

function Invoke-SoAIInstallCommandOnce {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$PackageCache
    )
    $alias = New-TemporaryInstallDrive -Root $Root
    $aliasRoot = $alias.Root
    $shortTempRoot = $null
    try {
        $pythonExe = Resolve-ChildPath -Root $Root -Child 'python\python.exe'
        $backendMain = Join-Path $aliasRoot 'backend\main.py'
        $venvPath = Join-Path $aliasRoot 'soai_main_venv'
        $venvPython = Join-Path $venvPath 'Scripts\python.exe'
        $realVenvPath = Resolve-ChildPath -Root $Root -Child 'soai_main_venv'
        $realVenvPython = Resolve-ChildPath -Root $Root -Child 'soai_main_venv\Scripts\python.exe'
        $stateDir = Join-Path $aliasRoot 'data\state'
        $locksDir = Join-Path $stateDir 'locks'
        $playwrightDir = Join-Path $stateDir 'playwright-browsers'
        $realStateDir = Resolve-ChildPath -Root $Root -Child 'data\state'
        $realLocksDir = Resolve-ChildPath -Root $Root -Child 'data\state\locks'
        $realPlaywrightDir = Resolve-ChildPath -Root $Root -Child 'data\state\playwright-browsers'
        $realJavaDir = Join-Path $realStateDir 'java'
        $realTikaDir = Join-Path $realStateDir 'tika'
        if (!(Test-Path -LiteralPath $pythonExe)) {
            throw "SoAI app-local Python was not found: $pythonExe"
        }
        if (!(Test-Path -LiteralPath $backendMain)) {
            throw "SoAI backend entrypoint was not found: $backendMain"
        }

        Set-InstallProgress -Progress 60 -Message 'Creating the SoAI managed Python environment.'
        $shortTempRoot = Join-Path $env:TEMP ("SoAI-Install-" + [Guid]::NewGuid().ToString('N').Substring(0, 12))
        $shortTemp = Join-Path $shortTempRoot 'tmp'
        New-Item -ItemType Directory -Force -Path $shortTemp | Out-Null

        $envValues = @{
            SOAI_TMP_DIR = $shortTemp
            TMPDIR = $shortTemp
            TEMP = $shortTemp
            TMP = $shortTemp
            PATH = Get-SoAIProcessPath -Root $Root
            PIP_CACHE_DIR = $PackageCache
            PIP_DEFAULT_TIMEOUT = '120'
            SOAI_VENV_PATH = $venvPath
            SOAI_STATE_DIR = $stateDir
            SOAI_LOCKS_PATH = $locksDir
            PLAYWRIGHT_BROWSERS_PATH = $playwrightDir
        }
        $phaseScripts = Write-PythonPhaseScripts -Root $Root
        $aliasRepoRoot = $alias.Root.TrimEnd('\')
        $realRepoRoot = Resolve-FullPath $Root
        $aliasEnvValues = $envValues.Clone()
        $aliasEnvValues['PYTHONPATH'] = Join-Path $aliasRepoRoot 'backend'

        Invoke-LoggedCommand `
            -Root $Root `
            -PhaseName 'create-managed-venv' `
            -WorkingDirectory $alias.Root `
            -Executable $pythonExe `
            -Arguments @($phaseScripts.CreateVenv, $realRepoRoot) `
            -EnvironmentValues $aliasEnvValues `
            -TimeoutSeconds 1200 `
            -HeartbeatSeconds 30 `
            -HeartbeatMessage 'Creating the SoAI managed Python environment' `
            -ProgressStart 60 `
            -ProgressEnd 66 | Out-Null
        Copy-AppLocalPythonRuntimeDlls -Root $Root
        Copy-AppLocalVisualCppRuntimeDlls -Root $Root

        Invoke-LoggedCommand `
            -Root $Root `
            -PhaseName 'install-python-deps' `
            -WorkingDirectory $alias.Root `
            -Executable $venvPython `
            -Arguments @($phaseScripts.InstallDeps, $aliasRepoRoot) `
            -EnvironmentValues $aliasEnvValues `
            -TimeoutSeconds $DependencyInstallTimeoutSeconds `
            -HeartbeatSeconds 30 `
            -HeartbeatMessage 'Installing SoAI Python dependencies' `
            -ProgressStart 66 `
            -ProgressEnd 82 | Out-Null

        $realEnvValues = @{
            SOAI_TMP_DIR = $shortTemp
            TMPDIR = $shortTemp
            TEMP = $shortTemp
            TMP = $shortTemp
            PATH = Get-SoAIProcessPath -Root $Root
            PIP_CACHE_DIR = $PackageCache
            PIP_DEFAULT_TIMEOUT = '120'
            SOAI_VENV_PATH = $realVenvPath
            SOAI_STATE_DIR = $realStateDir
            SOAI_LOCKS_PATH = $realLocksDir
            PLAYWRIGHT_BROWSERS_PATH = $realPlaywrightDir
            PYTHONPATH = Resolve-ChildPath -Root $Root -Child 'backend'
        }

        for ($artifactAttempt = 1; $artifactAttempt -le 2; $artifactAttempt += 1) {
            try {
                Invoke-LoggedCommand `
                    -Root $Root `
                    -PhaseName 'install-runtime-artifacts' `
                    -WorkingDirectory $realRepoRoot `
                    -Executable $realVenvPython `
                    -Arguments @($phaseScripts.InstallArtifacts, $realRepoRoot) `
                    -EnvironmentValues $realEnvValues `
                    -TimeoutSeconds $DependencyInstallTimeoutSeconds `
                    -ProgressPaths @($realPlaywrightDir, $realJavaDir, $realTikaDir) `
                    -NoProgressTimeoutSeconds 300 `
                    -HeartbeatSeconds 30 `
                    -HeartbeatMessage 'Preparing SoAI runtime artifacts' `
                    -ProgressStart 82 `
                    -ProgressEnd 92 | Out-Null
                break
            }
            catch {
                if ($artifactAttempt -eq 2) {
                    throw
                }
                Write-Step "Runtime artifact preparation failed: $($_.Exception.Message)"
                Write-Step 'Retrying runtime artifact preparation once without rebuilding the managed Python environment...'
            }
        }

        Invoke-LoggedCommand `
            -Root $Root `
            -PhaseName 'post-update-hook' `
            -WorkingDirectory $realRepoRoot `
            -Executable $realVenvPython `
            -Arguments @('-P', '-m', 'app.updater.post_update_hook') `
            -EnvironmentValues $realEnvValues `
            -TimeoutSeconds 1200 `
            -HeartbeatSeconds 30 `
            -HeartbeatMessage 'Finalizing SoAI installation' `
            -ProgressStart 92 `
            -ProgressEnd 95 | Out-Null
    }
    finally {
        Remove-TemporaryInstallDrive -Drive $alias.Drive
        if ($shortTempRoot) {
            Remove-DirectoryTree -Path $shortTempRoot
        }
    }
}

function Invoke-SoAIInstallCommand {
    param([Parameter(Mandatory=$true)][string]$Root)
    $pythonExe = Resolve-ChildPath -Root $Root -Child 'python\python.exe'
    if (!(Test-Path -LiteralPath $pythonExe)) {
        throw "SoAI app-local Python was not found: $pythonExe"
    }
    $packageCache = Join-Path $env:TEMP ("SoAI-Packages-" + [Guid]::NewGuid().ToString('N'))
    if (Test-Path -LiteralPath $packageCache) {
        throw 'The private installer package cache path already exists.'
    }
    $cacheSecurity = New-Object Security.AccessControl.DirectorySecurity
    $cacheSecurity.SetAccessRuleProtection($true, $false)
    $cacheOwner = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $cacheSecurity.SetOwner($cacheOwner)
    $cacheRule = New-Object Security.AccessControl.FileSystemAccessRule(
        $cacheOwner,
        [Security.AccessControl.FileSystemRights]::FullControl,
        [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit',
        [Security.AccessControl.PropagationFlags]::None,
        [Security.AccessControl.AccessControlType]::Allow
    )
    $cacheSecurity.AddAccessRule($cacheRule)
    [void][IO.Directory]::CreateDirectory($packageCache, $cacheSecurity)
    try {
        Remove-IncompleteManagedVenv -Root $Root
        for ($attempt = 1; $attempt -le 2; $attempt += 1) {
            Remove-LocalPackageBuildArtifacts -Root $Root
            try {
                Invoke-SoAIInstallCommandOnce -Root $Root -PackageCache $packageCache
                Remove-LocalPackageBuildArtifacts -Root $Root
                return
            }
            catch {
                Remove-LocalPackageBuildArtifacts -Root $Root
                if ($attempt -eq 2 -or $script:LastFailedInstallPhase -in @('install-runtime-artifacts', 'post-update-hook')) {
                    throw
                }
                Write-Step "SoAI managed environment preparation failed: $($_.Exception.Message)"
                Write-Step 'Rebuilding the SoAI managed Python environment once...'
                Remove-DirectoryTree -Path (Resolve-ChildPath -Root $Root -Child 'soai_main_venv')
            }
        }
    }
    finally {
        Remove-DirectoryTree -Path $packageCache
    }
}

function Write-InstallState {
    param([Parameter(Mandatory=$true)][string]$Root)
    $stateDir = Resolve-ChildPath -Root $Root -Child 'data\state'
    New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
    $pythonExe = Resolve-ChildPath -Root $Root -Child 'python\python.exe'
    $venvPython = Resolve-ChildPath -Root $Root -Child 'soai_main_venv\Scripts\python.exe'
    $state = @{
        product = 'SoAI'
        installed_at_utc = [DateTime]::UtcNow.ToString('o')
        python_runtime = (& $pythonExe --version 2>&1) -join ' '
        managed_python = (& $venvPython --version 2>&1) -join ' '
        webview2_runtime = Get-WebView2RuntimeVersion
    } | ConvertTo-Json -Depth 3
    Set-Content -LiteralPath (Join-Path $stateDir 'windows-install.json') -Value $state -Encoding UTF8
}

function Grant-RuntimeWriteAccess {
    param([Parameter(Mandatory=$true)][string]$Root)
    $usersSidGrant = '*S-1-5-32-545:(OI)(CI)M'
    foreach ($relative in @('data', 'soai_main_venv', 'python')) {
        $path = Resolve-ChildPath -Root $Root -Child $relative
        if (!$path.StartsWith('\\?\', [StringComparison]::Ordinal)) {
            if ($path.StartsWith('\\', [StringComparison]::Ordinal)) {
                $path = '\\?\UNC\' + $path.Substring(2)
            }
            else {
                $path = '\\?\' + $path
            }
        }
        if (!(Test-Path -LiteralPath $path -PathType Container)) {
            continue
        }
        & "$env:WINDIR\System32\icacls.exe" $path /grant $usersSidGrant /T | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to grant standard user write access to SoAI runtime directory: $path"
        }
    }
}

function Test-SQLiteRuntimeAccess {
    param([Parameter(Mandatory=$true)][string]$Root)
    foreach ($relativePython in @('python\python.exe', 'soai_main_venv\Scripts\python.exe')) {
        $pythonExe = Resolve-ChildPath -Root $Root -Child $relativePython
        & $pythonExe -c 'import sqlite3; print(sqlite3.sqlite_version)' | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "SoAI SQLite runtime validation failed for: $pythonExe"
        }
    }
}

$resolvedInstallRoot = Resolve-FullPath $InstallRoot
try {
    Set-InstallProgress -Progress 35 -Message "Preparing SoAI in $resolvedInstallRoot"
    Set-InstallProgress -Progress 38 -Message 'Checking Microsoft Edge WebView2 Runtime...'
    Install-WebView2Runtime
    Set-InstallProgress -Progress 43 -Message 'Preparing Microsoft Visual C++ runtime support...'
    Install-VisualCppRuntime -Root $resolvedInstallRoot
    Set-InstallProgress -Progress 48 -Message "Preparing app-local Python $PythonVersion runtime..."
    Install-PythonRuntime -Root $resolvedInstallRoot
    Copy-AppLocalVisualCppRuntimeDlls -Root $resolvedInstallRoot
    Set-InstallProgress -Progress 55 -Message 'Preparing SoAI bootstrap dependencies...'
    Install-Stage0BootstrapDependencies -Root $resolvedInstallRoot
    if ($BootstrapOnly) {
        Set-InstallProgress -Progress 98 -Message 'SoAI bootstrap runtime is ready.'
    }
    else {
        Invoke-SoAIInstallCommand -Root $resolvedInstallRoot
        Set-InstallProgress -Progress 96 -Message 'Writing SoAI installation state...'
        Write-InstallState -Root $resolvedInstallRoot
        Set-InstallProgress -Progress 97 -Message 'Configuring SoAI runtime permissions...'
        Grant-RuntimeWriteAccess -Root $resolvedInstallRoot
        Test-SQLiteRuntimeAccess -Root $resolvedInstallRoot
        Set-InstallProgress -Progress 98 -Message 'SoAI is ready to start.'
    }
}
finally {
    Remove-DirectoryTree -Path $script:InstallerDownloadRoot
    Remove-DirectoryTree -Path $script:ReleasedInstallerDownloadRoot
}
exit 0
