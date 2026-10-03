[CmdletBinding()]
param(
    [string]$InstallRoot,
    [string]$PythonVersion,
    [string]$PythonUrl,
    [string]$PythonSha256,
    [string]$WebView2BootstrapperUrl = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703',
    [string]$VisualCppRedistUrl = 'https://aka.ms/vs/17/release/vc_redist.x64.exe',
    [string]$VisualCppAppLocalUrl = 'https://www.nuget.org/api/v2/package/VCLibs.VCRuntime.140/1.0.4',
    [string]$VisualCppAppLocalSha256 = 'EA8FAD02D8DE9CA1AB4E1D20C282166B3386ADF91A9B143019D59507229EA375',
    [string]$StatusPath,
    [string]$DiagnosticRoot,
    [int]$DependencyInstallTimeoutSeconds = 7200,
    [switch]$BootstrapOnly,
    [switch]$PreflightOnly
)

function Resolve-FullPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $executionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
}

function Resolve-NativePath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $absolute = Resolve-FullPath $Path
    if ($absolute.StartsWith('\\?\', [StringComparison]::Ordinal)) { return $absolute }
    if ($absolute.StartsWith('\\', [StringComparison]::Ordinal)) { return '\\?\UNC\' + $absolute.Substring(2) }
    return '\\?\' + $absolute
}

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($PreflightOnly -and $BootstrapOnly) {
    throw 'PreflightOnly and BootstrapOnly are mutually exclusive.'
}
if ($PreflightOnly -or $BootstrapOnly) {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    try {
        $principal = [Security.Principal.WindowsPrincipal]::new($identity)
        if (!$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            throw 'Windows runtime preflight and bootstrap require an elevated administrator process.'
        }
    }
    finally { $identity.Dispose() }
}
if ($PreflightOnly) {
    if (![string]::IsNullOrWhiteSpace($InstallRoot)) {
        $sourceRoot = Resolve-FullPath $InstallRoot
        $sourceIdentity = [IO.File]::ReadAllText((Resolve-NativePath (Join-Path $sourceRoot 'release-info-v1.json'))) | ConvertFrom-Json
        $sourceFields = @($sourceIdentity.PSObject.Properties.Name | Sort-Object)
        $expectedFields = @('artifact_type', 'core_version', 'edition', 'product', 'schema_version', 'version')
        $sourceVersion = [IO.File]::ReadAllText((Resolve-NativePath (Join-Path $sourceRoot 'VERSION'))).Trim()
        $controlPath = Resolve-NativePath (Join-Path $sourceRoot 'soai.exe')
        [Reflection.Assembly]::Load([IO.File]::ReadAllBytes($controlPath)) | Out-Null
        if ($sourceFields.Count -ne 6 -or (Compare-Object $sourceFields $expectedFields -CaseSensitive).Count -ne 0 -or
            $sourceIdentity.product -isnot [string] -or ![string]::Equals($sourceIdentity.product, 'SoAI', [StringComparison]::Ordinal) -or
            $sourceIdentity.edition -isnot [string] -or ![string]::Equals($sourceIdentity.edition, 'soai-core', [StringComparison]::Ordinal) -or
            $sourceIdentity.artifact_type -isnot [string] -or ![string]::Equals($sourceIdentity.artifact_type, 'complete', [StringComparison]::Ordinal) -or
            $sourceIdentity.schema_version -isnot [int] -or $sourceIdentity.schema_version -ne 1 -or
            $sourceIdentity.version -isnot [string] -or ![string]::Equals($sourceIdentity.version, $sourceVersion, [StringComparison]::Ordinal) -or
            $sourceIdentity.core_version -isnot [string] -or ![string]::Equals($sourceIdentity.core_version, $sourceVersion, [StringComparison]::Ordinal) -or
            ![SoAILauncher.ReleaseVersionText]::IsValid($sourceVersion) -or
            ![IO.File]::Exists((Resolve-NativePath (Join-Path $sourceRoot 'backend\main.py')))) {
            throw 'Missing-Python bootstrap requires a complete SoAI Core release payload with matching identity.'
        }
        Write-Host '[SoAI] Complete source payload identity is verified.'
    }
    $machine = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::LocalMachine,
        [Microsoft.Win32.RegistryView]::Registry64
    )
    try {
        $filesystem = $machine.OpenSubKey('SYSTEM\CurrentControlSet\Control\FileSystem', $true)
        if ($null -eq $filesystem) { throw 'Windows filesystem policy registry key is unavailable.' }
        try {
            $value = $filesystem.GetValue('LongPathsEnabled', $null)
            if ($null -ne $value) {
                if ($filesystem.GetValueKind('LongPathsEnabled') -ne [Microsoft.Win32.RegistryValueKind]::DWord -or
                    $value -notin @(0, 1)) {
                    throw 'LongPathsEnabled must be a DWORD with value zero or one. Repair the machine policy before installing SoAI.'
                }
            }
            if ($null -eq $value -or $value -eq 0) {
                $filesystem.SetValue('LongPathsEnabled', 1, [Microsoft.Win32.RegistryValueKind]::DWord)
                $filesystem.Flush()
            }
            if ($filesystem.GetValueKind('LongPathsEnabled') -ne [Microsoft.Win32.RegistryValueKind]::DWord -or
                $filesystem.GetValue('LongPathsEnabled', $null) -ne 1) {
                throw 'Windows long-path policy could not be verified after preflight.'
            }
        }
        finally { $filesystem.Dispose() }
    }
    finally { $machine.Dispose() }
    Write-Host '[SoAI] Windows long-path policy is enabled and verified.'
    exit 0
}
if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    throw 'InstallRoot is required for runtime provisioning.'
}
$script:InstallProgress = 35
$script:InstallStatusMessage = ''
$script:InstallStatusDetail = ''
$script:InstallStatusMessageLimit = 110
$script:InstallStatusDetailLimit = 150
$script:InstallerDownloadRoot = Join-Path $env:TEMP (
    "SoAI-Installer-" + [Guid]::NewGuid().ToString('N')
)
$script:ReleasedInstallerDownloadRoot = Join-Path $env:TEMP 'SoAI-Installer'
foreach ($retryVariable in @('PIP_RETRIES', 'PIP_RESUME_RETRIES')) {
    if ($null -eq [Environment]::GetEnvironmentVariable($retryVariable, 'Process')) {
        [Environment]::SetEnvironmentVariable($retryVariable, '10', 'Process')
    }
}

function Write-InstallerConsoleMessage {
    param([Parameter(Mandatory=$true)][AllowEmptyString()][string]$Message)
    if ($Message.Length -eq 0) {
        Write-Host ''
        return
    }
    $offset = 0
    while ($offset -lt $Message.Length) {
        $length = [Math]::Min(1000, $Message.Length - $offset)
        if ($offset + $length -lt $Message.Length -and
            [char]::IsHighSurrogate($Message[$offset + $length - 1]) -and
            [char]::IsLowSurrogate($Message[$offset + $length])) {
            $length -= 1
        }
        Write-Host ($Message.Substring($offset, $length))
        $offset += $length
    }
}

function Write-Step {
    param([Parameter(Mandatory=$true)][string]$Message)
    Write-InstallerConsoleMessage "[SoAI] $Message"
    Write-InstallStatus -Message $Message
}

function Set-InstallProgress {
    param(
        [Parameter(Mandatory=$true)][int]$Progress,
        [string]$Message,
        [AllowEmptyString()][string]$Detail
    )
    $script:InstallProgress = [Math]::Max(35, [Math]::Min(95, $Progress))
    if (![string]::IsNullOrWhiteSpace($Message)) {
        Write-Step $Message
    }
    elseif ($PSBoundParameters.ContainsKey('Detail')) {
        Write-InstallStatus -Detail $Detail
    }
    else {
        Write-InstallStatus
    }
}

function Write-InstallStatus {
    param(
        [string]$Message,
        [AllowEmptyString()][string]$Detail
    )
    if ([string]::IsNullOrWhiteSpace($StatusPath)) {
        return
    }
    try {
        $statusDir = Split-Path -Parent $StatusPath
        New-Item -ItemType Directory -Force -Path $statusDir | Out-Null
        if (![string]::IsNullOrWhiteSpace($Message)) {
            $script:InstallStatusMessage = Compress-InstallerStatusText -Text (ConvertFrom-InstallerTerminalText $Message) -Limit $script:InstallStatusMessageLimit
            $script:InstallStatusDetail = ''
        }
        if ($PSBoundParameters.ContainsKey('Detail')) {
            $script:InstallStatusDetail = Compress-InstallerStatusText -Text (ConvertFrom-InstallerTerminalText $Detail) -Limit $script:InstallStatusDetailLimit
        }
        $tempPath = "$StatusPath.tmp"
        @(
            '[status]'
            "progress=$script:InstallProgress"
            "message=$script:InstallStatusMessage"
            "detail=$script:InstallStatusDetail"
            "updated_at_utc=$([DateTime]::UtcNow.ToString('o'))"
        ) | Set-Content -LiteralPath $tempPath -Encoding Unicode
        Move-Item -LiteralPath $tempPath -Destination $StatusPath -Force
    }
    catch {
    }
}

function Read-InstallerLogTail {
    param(
        [Parameter(Mandatory=$true)][string]$LogPath,
        [int]$LineCount = 80,
        [switch]$IncludeUnterminated
    )
    try {
        $stream = [IO.File]::Open($LogPath, [IO.FileMode]::Open, [IO.FileAccess]::Read, ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    }
    catch {
        return
    }
    try {
        $start = [Math]::Max([long]0, $stream.Length - 65536)
        $buffer = New-Object byte[] ([int]($stream.Length - $start))
        [void]$stream.Seek($start, [IO.SeekOrigin]::Begin)
        $read = 0
        while ($read -lt $buffer.Length) {
            $count = $stream.Read($buffer, $read, $buffer.Length - $read)
            if ($count -le 0) {
                break
            }
            $read += $count
        }
    }
    finally {
        $stream.Dispose()
    }
    if ($read -eq 0) {
        return
    }
    $end = $read
    if (!$IncludeUnterminated) {
        $end = [Array]::LastIndexOf($buffer, [byte]10, $read - 1) + 1
    }
    $begin = 0
    if ($start -gt 0) {
        $begin = [Array]::IndexOf($buffer, [byte]10, 0, $end) + 1
    }
    if ($begin -le 0 -and $start -gt 0) {
        return
    }
    if ($end -le $begin) {
        return
    }
    try {
        $text = (New-Object Text.UTF8Encoding($false, $true)).GetString($buffer, $begin, $end - $begin)
    }
    catch {
        $text = [Text.Encoding]::Default.GetString($buffer, $begin, $end - $begin)
    }
    $lines = @($text.TrimStart([char]0xFEFF).Split([char]10) |
        ForEach-Object { $_.TrimEnd([char]13) } |
        Where-Object { $_.Trim().Length -gt 0 })
    $lines | Select-Object -Last $LineCount
}

function ConvertFrom-InstallerTerminalText {
    param([AllowNull()][AllowEmptyString()][string]$Value)
    if ([string]::IsNullOrEmpty($Value)) {
        return ''
    }
    $text = $Value -replace '\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', ''
    $text = $text -replace '\x1b\[[0-?]*[ -/]*[@-~]', ''
    $text = $text -replace '\x1b[@-_]', ''
    $segments = @($text.Split([char]13) | Where-Object { $_.Trim().Length -gt 0 })
    if ($segments.Count -eq 0) {
        return ''
    }
    $text = [regex]::Replace(
        $segments[$segments.Count - 1],
        '\\(?:u([0-9A-Fa-f]{4})|U([0-9A-Fa-f]{8}))',
        [Text.RegularExpressions.MatchEvaluator]{
            param($match)
            if ($match.Groups[1].Success) {
                $digits = $match.Groups[1].Value
            }
            else {
                $digits = $match.Groups[2].Value
            }
            $codePoint = [Convert]::ToInt32($digits, 16)
            if ($codePoint -lt 0x80 -or $codePoint -gt 0x10FFFF -or ($codePoint -ge 0xD800 -and $codePoint -le 0xDFFF)) {
                return $match.Value
            }
            return [char]::ConvertFromUtf32($codePoint)
        }
    )
    $text = $text -replace '\p{Cc}', ' '
    $text = $text.Replace('\\\\?\\UNC\\', '\\\\').Replace('\\\\?\\', '').Replace('\\?\UNC\', '\\').Replace('\\?\', '')
    return ($text -replace '\s+', ' ').Trim()
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

function ConvertTo-InstallerLogEntry {
    param([AllowNull()][AllowEmptyString()][string]$Line)
    if ([string]::IsNullOrWhiteSpace($Line) -or $Line -match '^\s') {
        return $null
    }
    $text = ConvertFrom-InstallerTerminalText $Line
    if ($text.Length -eq 0) {
        return $null
    }
    $text = Format-SoAILogLine $text
    if ($text -match '^Traceback \(most recent call last\)') {
        return $null
    }
    $source = ''
    $sourceMatch = [regex]::Match($text, '^([A-Za-z][\w.+-]{1,31}):\s+(.+)$')
    if ($sourceMatch.Success) {
        $source = $sourceMatch.Groups[1].Value + ': '
        $text = $sourceMatch.Groups[2].Value
    }
    $text = $text -replace '[\u2500-\u25FF\u2800-\u28FF]', ' '
    $text = $text -replace '[-=#*_~^>|+]{3,}', ' '
    $text = $text -replace '\[\s*\]|\(\s*\)|\|\s*\|', ' '
    $text = $text -replace '(?<!\S)[|\[\]]+(?!\S)', ' '
    $text = ($text -replace '\s+', ' ').Trim()
    if ($text -notmatch '[\p{L}\p{N}]') {
        return $null
    }
    $isProgress = ($text -match '\d') -and ($text -notmatch '\p{L}{4,}')
    if (!$isProgress -and ($text -notmatch '\s' -or $text -match '^\[[A-Za-z]+\]\s')) {
        return $null
    }
    return [pscustomobject]@{
        Source = $source
        Text = $text
        IsProgress = $isProgress
    }
}

function Get-InstallerLogActivity {
    param([Parameter(Mandatory=$true)][string]$LogPath)
    $lines = @(Read-InstallerLogTail -LogPath $LogPath -LineCount 200)
    $progress = $null
    for ($index = $lines.Count - 1; $index -ge 0; $index -= 1) {
        $entry = ConvertTo-InstallerLogEntry $lines[$index]
        if ($null -eq $entry) {
            continue
        }
        if ($entry.IsProgress) {
            if ($null -eq $progress) {
                $progress = $entry
            }
            continue
        }
        if ($null -eq $progress) {
            return $entry.Source + $entry.Text
        }
        if ($entry.Source -eq $progress.Source) {
            $suffix = ' ' + [char]0x2014 + ' ' + (Compress-InstallerStatusText -Text $progress.Text -Limit ([int]($script:InstallStatusDetailLimit / 3)))
            return (Compress-InstallerStatusText -Text ($entry.Source + $entry.Text) -Limit ($script:InstallStatusDetailLimit - $suffix.Length)) + $suffix
        }
        break
    }
    if ($null -ne $progress) {
        return $progress.Source + $progress.Text
    }
    return ''
}

function Get-CommandActivity {
    param(
        [Parameter(Mandatory=$true)][string]$StdoutLogPath,
        [Parameter(Mandatory=$true)][string]$StderrLogPath
    )
    $activity = Get-InstallerLogActivity -LogPath $StderrLogPath
    if ([string]::IsNullOrWhiteSpace($activity)) {
        $activity = Get-InstallerLogActivity -LogPath $StdoutLogPath
    }
    return $activity
}

function Compress-InstallerStatusToken {
    param([Parameter(Mandatory=$true)][string]$Token)
    $ellipsis = [string][char]0x2026
    $compact = [regex]::Replace(
        $Token,
        '[0-9A-Fa-f]{32,}',
        [Text.RegularExpressions.MatchEvaluator]{
            param($match)
            return $match.Value.Substring(0, 12) + [char]0x2026
        }
    )
    if ($compact.Length -le 40) {
        return $compact
    }
    $url = [regex]::Match($compact, '^(\W*[A-Za-z][A-Za-z0-9+.-]*://[^/?#]+)([/?#].*)?$')
    if ($url.Success) {
        $segments = @(($url.Groups[2].Value -split '[?#]', 2)[0] -split '/' | Where-Object { $_.Length -gt 0 })
        $compact = $url.Groups[1].Value
        if ($segments.Count -gt 1) {
            $compact += '/' + $ellipsis + '/' + $segments[$segments.Count - 1]
        }
        elseif ($segments.Count -eq 1) {
            $compact += '/' + $segments[0]
        }
    }
    else {
        foreach ($separator in @('\', '/')) {
            $segments = @($compact -split [regex]::Escape($separator) | Where-Object { $_.Length -gt 0 })
            if ($segments.Count -gt 2) {
                $compact = $segments[0] + $separator + $ellipsis + $separator + $segments[$segments.Count - 1]
                break
            }
        }
    }
    if ($compact.Length -le 60) {
        return $compact
    }
    return $compact.Substring(0, 29) + $ellipsis + $compact.Substring($compact.Length - 30)
}

function Compress-InstallerStatusText {
    param(
        [AllowNull()][AllowEmptyString()][string]$Text,
        [Parameter(Mandatory=$true)][int]$Limit
    )
    $tokens = @(([string]$Text) -split ' ' | Where-Object { $_.Length -gt 0 } | ForEach-Object { Compress-InstallerStatusToken $_ })
    $compact = $tokens -join ' '
    if ($compact.Length -le $Limit) {
        return $compact
    }
    $cut = $compact.LastIndexOf(' ', $Limit - 1)
    if ($cut -lt ($Limit / 2)) {
        $cut = $Limit - 1
    }
    if ([char]::IsHighSurrogate($compact[$cut - 1])) {
        $cut -= 1
    }
    return $compact.Substring(0, $cut).TrimEnd(' ', ',', ';', ':') + [char]0x2026
}

function Get-UsefulLogTailMessage {
    param([Parameter(Mandatory=$true)][string]$LogPath)
    if (!(Test-Path -LiteralPath $LogPath)) {
        return ''
    }
    $lines = @(Read-InstallerLogTail -LogPath $LogPath -LineCount 80 -IncludeUnterminated)
    $insideFailedCommandTraceback = $false
    for ($index = $lines.Count - 1; $index -ge 0; $index -= 1) {
        $line = ConvertFrom-InstallerTerminalText $lines[$index]
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        $formatted = Format-SoAILogLine $line
        if ([string]::IsNullOrWhiteSpace($formatted)) {
            continue
        }
        if ($formatted -match '^Traceback\b') {
            $insideFailedCommandTraceback = $false
            continue
        }
        if ($insideFailedCommandTraceback -or $formatted -match '^\s*File\s+"' -or $formatted -match '^(?:During handling of the above exception|The above exception was the direct cause)') {
            continue
        }
        $exceptionMatch = [regex]::Match($formatted, '^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)):\s*(.+)$')
        if ($exceptionMatch.Success) {
            if ($exceptionMatch.Groups[1].Value -ceq 'subprocess.CalledProcessError') {
                $insideFailedCommandTraceback = $true
                continue
            }
            return $exceptionMatch.Groups[2].Value.Trim()
        }
        return $formatted.Trim()
    }
    return ''
}

function Get-InstallLogDir {
    param([Parameter(Mandatory=$true)][string]$Root)
    if ([string]::IsNullOrWhiteSpace($DiagnosticRoot)) {
        $logDir = Resolve-ChildPath -Root $Root -Child 'installer-support\logs'
    }
    else {
        $logDir = [IO.Path]::GetFullPath($DiagnosticRoot)
    }
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
    Write-InstallerConsoleMessage "[SoAI] Last lines from $(Split-Path -Leaf $LogPath):"
    Read-InstallerLogTail -LogPath $LogPath -LineCount $LineCount -IncludeUnterminated |
        ForEach-Object {
            if ($_ -ne $null -and $_.ToString().Trim().Length -gt 0) {
                Write-InstallerConsoleMessage (Format-SoAILogLine $_.ToString())
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
    $logAttempt = 1
    do {
        if ($logAttempt -eq 1) {
            $attemptSuffix = ''
        }
        else {
            $attemptSuffix = ".attempt-$logAttempt"
        }
        $stdoutLogPath = Join-Path $logDir "$safePhase$attemptSuffix.out.log"
        $stderrLogPath = Join-Path $logDir "$safePhase$attemptSuffix.err.log"
        $outcomeLogPath = Join-Path $logDir "$safePhase$attemptSuffix.command.json"
        if (!(Test-Path -LiteralPath $stdoutLogPath) -and !(Test-Path -LiteralPath $stderrLogPath) -and !(Test-Path -LiteralPath $outcomeLogPath)) {
            break
        }
        $logAttempt += 1
    } while ($logAttempt -le 10000)
    if ($logAttempt -gt 10000) {
        throw "Could not allocate a diagnostic log set for installer phase: $PhaseName"
    }
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
    $job = $null
    $exitCode = $null
    $failureMessage = $null
    $commandState = 'not-started'
    $script:LastFailedInstallPhase = $null
    if ($ProgressStart -gt 0) {
        Set-InstallProgress -Progress $ProgressStart -Message $HeartbeatMessage
    }
    try {
        $job = [SoAILauncher.NativeBackendJob]::StartLoggedProcess($psi, $stdoutLogPath, $stderrLogPath)
        $process = $job.ProcessHandle
        $commandState = 'running'
        $deadlineUtc = [DateTime]::UtcNow.AddSeconds([Math]::Max(60, $TimeoutSeconds))
        $progressDeadlineEnabled = $NoProgressTimeoutSeconds -gt 0
        $progressWatchPaths = @($stdoutLogPath, $stderrLogPath) + @($ProgressPaths)
        $lastProgressFingerprint = Get-ProgressFingerprint -Paths $progressWatchPaths
        $lastProgressUtc = [DateTime]::UtcNow
        $startedUtc = [DateTime]::UtcNow
        $nextHeartbeatUtc = $startedUtc.AddSeconds($HeartbeatSeconds)
        $nextFingerprintUtc = $startedUtc.AddSeconds(5)
        $lastActivity = $null
        $lastProgress = $script:InstallProgress
        while (!$process.WaitForExit(1000)) {
            $nowUtc = [DateTime]::UtcNow
            if ($HeartbeatSeconds -gt 0 -and $nowUtc -ge $nextHeartbeatUtc) {
                $currentProgress = $script:InstallProgress
                if ($ProgressStart -gt 0 -and $ProgressEnd -gt $ProgressStart) {
                    $expectedSeconds = [Math]::Min([Math]::Max(900, $TimeoutSeconds / 4), 1800)
                    $fraction = [Math]::Min(0.95, [Math]::Max(0.0, ($nowUtc - $startedUtc).TotalSeconds / $expectedSeconds))
                    $currentProgress = $ProgressStart + [int][Math]::Floor(($ProgressEnd - $ProgressStart - 1) * $fraction)
                }
                $activity = Get-CommandActivity -StdoutLogPath $stdoutLogPath -StderrLogPath $stderrLogPath
                if ($activity -cne $lastActivity -or $currentProgress -ne $lastProgress) {
                    Set-InstallProgress -Progress $currentProgress -Detail $activity
                    $lastActivity = $activity
                    $lastProgress = $currentProgress
                }
                $nextHeartbeatUtc = $nowUtc.AddSeconds($HeartbeatSeconds)
            }
            if ($nowUtc -gt $deadlineUtc) {
                $commandState = 'timed-out'
                throw "SoAI $PhaseName did not finish within $TimeoutSeconds seconds."
            }
            if ($progressDeadlineEnabled -and $nowUtc -ge $nextFingerprintUtc) {
                $nextFingerprintUtc = $nowUtc.AddSeconds(5)
                $fingerprint = Get-ProgressFingerprint -Paths $progressWatchPaths
                if ($fingerprint -ne $lastProgressFingerprint) {
                    $lastProgressFingerprint = $fingerprint
                    $lastProgressUtc = $nowUtc
                }
                elseif (($nowUtc - $lastProgressUtc).TotalSeconds -ge $NoProgressTimeoutSeconds) {
                    $commandState = 'stalled'
                    throw "SoAI $PhaseName made no observable progress for $NoProgressTimeoutSeconds seconds."
                }
            }
        }
        $exitCode = $job.ExitCode
        $commandState = if ($exitCode -eq 0) { 'succeeded' } else { 'failed' }
    }
    catch {
        $failureMessage = $_.Exception.ToString()
        if ($commandState -in @('not-started', 'running')) { $commandState = 'failed' }
        $script:LastFailedInstallPhase = $PhaseName
        throw
    }
    finally {
        try {
            if ($null -ne $job) { $job.Dispose() }
        }
        catch {
            $commandState = 'cleanup-failed'
            $failureMessage = @($failureMessage, $_.Exception.ToString()) -join "`n"
            $script:LastFailedInstallPhase = $PhaseName
            throw
        }
        finally {
            $outcome = [ordered]@{
                phase = $PhaseName
                executable = $Executable
                arguments = $Arguments
                working_directory = $WorkingDirectory
                state = $commandState
                exit_code = $exitCode
                failure = $failureMessage
                stdout = $stdoutLogPath
                stderr = $stderrLogPath
            } | ConvertTo-Json -Depth 5
            $outcomeStream = [IO.File]::Open($outcomeLogPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
            try {
                $bytes = [Text.Encoding]::UTF8.GetBytes($outcome)
                $outcomeStream.Write($bytes, 0, $bytes.Length)
                $outcomeStream.Flush($true)
            }
            finally { $outcomeStream.Dispose() }
        }
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
        Set-InstallProgress -Progress $ProgressEnd -Detail ''
    }
    else {
        Write-InstallStatus -Detail ''
    }
    $script:LastFailedInstallPhase = $null
    return $stdoutLogPath
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

function Download-File {
    param(
        [Parameter(Mandatory=$true)][string]$Uri,
        [Parameter(Mandatory=$true)][string]$Destination,
        [string]$Sha256,
        [ValidateSet('Exe','Zip')][string]$Kind = 'Exe'
    )
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    $temp = "$Destination.download"
    Write-Step "Downloading runtime component: $([IO.Path]::GetFileName($Destination))"
    $logDirectory = Get-InstallLogDir -Root $InstallRoot
    Invoke-SoAIHttpDownload -Uri $Uri -Destination $temp -TimeoutSeconds 600 -DiagnosticDirectory $logDirectory
    if ($Kind -eq 'Exe' -and !(Test-ExecutableHeader $temp)) {
        throw 'download did not look like a Windows executable'
    }
    if ($Kind -eq 'Zip' -and !(Test-ZipHeader $temp)) {
        throw 'download did not look like a zip package'
    }
    Assert-Hash -Path $temp -Sha256 $Sha256
    Move-Item -LiteralPath $temp -Destination $Destination -Force -ErrorAction Stop
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
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$PythonExe,
        [switch]$Required
    )
    if (![IO.File]::Exists((Resolve-NativePath $PythonExe))) {
        if ($Required) { throw "Python runtime validation failed: the executable is missing: $PythonExe" }
        return $false
    }
    try {
        $log = Invoke-LoggedCommand -Root $Root -PhaseName 'validate-python-runtime' `
            -WorkingDirectory ([Environment]::GetFolderPath('System')) -Executable $PythonExe `
            -Arguments @('--version') -EnvironmentValues @{} -TimeoutSeconds 60
        $output = ([string](Get-Content -LiteralPath $log -Raw -Encoding UTF8)).Trim()
        if ($output -ne "Python $PythonVersion") { throw "Python runtime version mismatch: expected Python $PythonVersion; received $output. Diagnostic output: $log" }
        return $true
    }
    catch {
        if ($Required) { throw }
        Write-Step "Existing Python runtime requires repair: $($_.Exception.Message)"
        return $false
    }
}

function Get-PackagedPythonRuntimePath {
    param([Parameter(Mandatory=$true)][string]$Root)
    $runtimeAssetsDirectory = Resolve-ChildPath -Root $Root -Child 'runtime-assets'
    $pythonAssetsDirectory = Resolve-ChildPath -Root $Root -Child 'runtime-assets\python'
    $platformDirectory = Resolve-ChildPath -Root $Root -Child 'runtime-assets\python\windows-x64'
    foreach ($directory in @($runtimeAssetsDirectory, $pythonAssetsDirectory)) {
        $item = Get-Item -LiteralPath $directory -Force -ErrorAction SilentlyContinue
        if ($null -eq $item) {
            return $null
        }
        if (!$item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Packaged Python runtime directory is unsafe: $directory"
        }
    }
    $platformItem = Get-Item -LiteralPath $platformDirectory -Force -ErrorAction SilentlyContinue
    if ($null -eq $platformItem) {
        return $null
    }
    if (!$platformItem.PSIsContainer -or ($platformItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Packaged Python runtime platform directory is unsafe: $platformDirectory"
    }
    $archivePath = Join-Path $platformDirectory "python-$PythonVersion.nupkg"
    $archiveItem = Get-Item -LiteralPath $archivePath -Force -ErrorAction SilentlyContinue
    if ($null -eq $archiveItem) {
        throw "Packaged Python runtime platform directory is incomplete: $platformDirectory"
    }
    if ($archiveItem.PSIsContainer -or ($archiveItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Packaged Python runtime archive is unsafe: $archivePath"
    }
    return $archivePath
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
    if (Test-PythonRuntime -Root $Root -PythonExe $pythonExe) {
        Write-Step "Python $PythonVersion runtime is already ready."
        Copy-AppLocalPythonRuntimeDlls -Root $Root
        return
    }

    $downloadDir = $script:InstallerDownloadRoot
    $package = Join-Path $downloadDir "python-$PythonVersion.nupkg"
    $packageZip = Join-Path $downloadDir "python-$PythonVersion.zip"
    $extractDir = Join-Path $downloadDir "python-$PythonVersion-package"
    New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
    $packagedRuntime = Get-PackagedPythonRuntimePath -Root $Root
    if ($null -ne $packagedRuntime) {
        Copy-Item -LiteralPath $packagedRuntime -Destination $package -Force
        Assert-Hash -Path $package -Sha256 $PythonSha256
    }
    elseif (!(Test-Path -LiteralPath $package)) {
        Download-File -Uri $PythonUrl -Destination $package -Sha256 $PythonSha256 -Kind Zip
    }
    else {
        Assert-Hash -Path $package -Sha256 $PythonSha256
    }

    if (Test-Path -LiteralPath $pythonDir) {
        Write-Step 'Removing incomplete Python runtime...'
        Remove-Item -LiteralPath $pythonDir -Recurse -Force
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
    [void](Test-PythonRuntime -Root $Root -PythonExe $pythonExe -Required)
    Copy-AppLocalPythonRuntimeDlls -Root $Root
}

function Install-Stage0BootstrapDependencies {
    param([Parameter(Mandatory=$true)][string]$Root)
    $pythonExe = Resolve-ChildPath -Root $Root -Child 'python\python.exe'
    Write-Step 'Preparing the SoAI stage-0 bootstrap dependencies...'
    Invoke-LoggedCommand -Root $Root -PhaseName 'install-stage0-dependencies' `
        -WorkingDirectory ([Environment]::GetFolderPath('System')) -Executable $pythonExe `
        -Arguments @('-m', 'pip', 'install', '--disable-pip-version-check', '--no-warn-script-location', '--upgrade',
            'ruamel-yaml==0.19.1', 'httpx2==2.10.0', 'filelock==3.32.2', 'psutil==7.2.2') `
        -EnvironmentValues @{ PYTHONUTF8 = '1'; PYTHONIOENCODING = 'utf-8' } `
        -TimeoutSeconds $DependencyInstallTimeoutSeconds -HeartbeatSeconds 2 `
        -HeartbeatMessage 'Preparing SoAI bootstrap dependencies' | Out-Null
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
    $resolvedRoot = [SoAILauncher.NativeBackendJob]::ResolveProcessPath((Resolve-FullPath $Root), $true)
    foreach ($code in ([int][char]'Z')..([int][char]'P')) {
        $letter = [char]$code
        $drive = "$letter`:"
        $driveRoot = "$drive\"
        if ([Environment]::GetLogicalDrives() -contains $driveRoot) {
            continue
        }
        try {
            Invoke-LoggedCommand -Root $Root -PhaseName "map-install-drive-$letter" `
                -WorkingDirectory ([Environment]::GetFolderPath('System')) `
                -Executable "$env:WINDIR\System32\subst.exe" -Arguments @($drive, $resolvedRoot) `
                -EnvironmentValues @{} -TimeoutSeconds 60 | Out-Null
        }
        catch {
            if (Test-Path -LiteralPath $driveRoot) { continue }
            throw
        }
        if (!(Test-Path -LiteralPath $driveRoot)) {
            Remove-TemporaryInstallDrive -Drive $drive -Root $Root
            throw "The successful temporary drive mapping could not be verified: $drive"
        }
        return @{
            Drive = $drive
            Root = $driveRoot
        }
    }
    throw 'No free drive letter was available for short-path dependency preparation.'
}

function Remove-TemporaryInstallDrive {
    param(
        [Parameter(Mandatory=$true)][string]$Drive,
        [Parameter(Mandatory=$true)][string]$Root
    )
    Invoke-LoggedCommand -Root $Root -PhaseName 'release-install-drive' `
        -WorkingDirectory ([Environment]::GetFolderPath('System')) `
        -Executable "$env:WINDIR\System32\subst.exe" -Arguments @($Drive, '/D') `
        -EnvironmentValues @{} -TimeoutSeconds 60 | Out-Null
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
            PYTHONUTF8 = '1'
            PYTHONIOENCODING = 'utf-8'
            SOAI_VENV_PATH = $realVenvPath
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
            -HeartbeatSeconds 2 `
            -HeartbeatMessage 'Creating the SoAI managed Python environment' `
            -ProgressStart 60 `
            -ProgressEnd 66 | Out-Null
        Copy-AppLocalPythonRuntimeDlls -Root $Root
        Copy-AppLocalVisualCppRuntimeDlls -Root $Root

        Invoke-LoggedCommand `
            -Root $Root `
            -PhaseName 'install-python-deps' `
            -WorkingDirectory $alias.Root `
            -Executable $realVenvPython `
            -Arguments @($phaseScripts.InstallDeps, $aliasRepoRoot) `
            -EnvironmentValues $aliasEnvValues `
            -TimeoutSeconds $DependencyInstallTimeoutSeconds `
            -HeartbeatSeconds 2 `
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
            PYTHONUTF8 = '1'
            PYTHONIOENCODING = 'utf-8'
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
                    -HeartbeatSeconds 2 `
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
            -HeartbeatSeconds 2 `
            -HeartbeatMessage 'Finalizing SoAI installation' `
            -ProgressStart 92 `
            -ProgressEnd 95 | Out-Null
    }
    finally {
        Remove-TemporaryInstallDrive -Drive $alias.Drive -Root $Root
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
    $runtimeVersionLog = Invoke-LoggedCommand -Root $Root -PhaseName 'installed-python-version' `
        -WorkingDirectory ([Environment]::GetFolderPath('System')) -Executable $pythonExe `
        -Arguments @('--version') -EnvironmentValues @{} -TimeoutSeconds 60
    $managedVersionLog = Invoke-LoggedCommand -Root $Root -PhaseName 'managed-python-version' `
        -WorkingDirectory ([Environment]::GetFolderPath('System')) -Executable $venvPython `
        -Arguments @('--version') -EnvironmentValues @{} -TimeoutSeconds 60
    $state = @{
        product = 'SoAI'
        installed_at_utc = [DateTime]::UtcNow.ToString('o')
        python_runtime = (Get-Content -LiteralPath $runtimeVersionLog -Raw -Encoding UTF8).Trim()
        managed_python = (Get-Content -LiteralPath $managedVersionLog -Raw -Encoding UTF8).Trim()
        webview2_runtime = Get-WebView2RuntimeVersion
    } | ConvertTo-Json -Depth 3
    Set-Content -LiteralPath (Join-Path $stateDir 'windows-install.json') -Value $state -Encoding UTF8
}

function Grant-RuntimeWriteAccess {
    param([Parameter(Mandatory=$true)][string]$Root)
    $usersSidGrant = '*S-1-5-32-545:(OI)(CI)M'
    foreach ($relative in @('data', 'soai_main_venv', 'python')) {
        $path = Resolve-NativePath (Resolve-ChildPath -Root $Root -Child $relative)
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
        $phase = if ($relativePython -eq 'python\python.exe') { 'runtime-sqlite-import' } else { 'managed-sqlite-import' }
        Invoke-LoggedCommand -Root $Root -PhaseName $phase `
            -WorkingDirectory ([Environment]::GetFolderPath('System')) -Executable $pythonExe `
            -Arguments @('-c', 'import sqlite3; print(sqlite3.sqlite_version)') `
            -EnvironmentValues @{} -TimeoutSeconds 60 | Out-Null
    }
}

$pythonParameters = @($PythonVersion, $PythonUrl, $PythonSha256)
$providedPythonParameters = @($pythonParameters | Where-Object { ![string]::IsNullOrWhiteSpace($_) })
if ($providedPythonParameters.Count -eq 0) {
    $dependencyPath = Join-Path $PSScriptRoot 'dependencies-v1.json'
    if (!(Test-Path -LiteralPath $dependencyPath -PathType Leaf)) {
        throw "Windows Python dependency metadata is missing: $dependencyPath"
    }
    $dependencyAuthority = Get-Content -LiteralPath $dependencyPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $pythonDependency = $dependencyAuthority.dependencies.python
    if ($null -eq $pythonDependency) {
        throw 'Windows Python dependency metadata is invalid.'
    }
    $pythonDependencyFields = @($pythonDependency.PSObject.Properties.Name | Sort-Object)
    if ($dependencyAuthority.schema_version -ne 1 `
        -or (Compare-Object $pythonDependencyFields @('package_sha256', 'url', 'version')).Count -ne 0) {
        throw 'Windows Python dependency metadata is invalid.'
    }
    $PythonVersion = $pythonDependency.version
    $PythonUrl = $pythonDependency.url
    $PythonSha256 = $pythonDependency.package_sha256
}
elseif ($providedPythonParameters.Count -ne 3) {
    throw 'Windows Python dependency parameters must be supplied together.'
}
if ($PythonVersion -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$' `
    -or $PythonUrl -notmatch '^https://' `
    -or $PythonSha256 -notmatch '^[0-9a-fA-F]{64}$') {
    throw 'Windows Python dependency metadata is invalid.'
}

$resolvedInstallRoot = Resolve-FullPath $InstallRoot
$nativeOwnerPath = Resolve-NativePath (Resolve-ChildPath -Root $resolvedInstallRoot -Child 'soai.exe')
[Reflection.Assembly]::Load([IO.File]::ReadAllBytes($nativeOwnerPath)) | Out-Null
try {
    [SoAILauncher.NativeBackendJob]::PrepareTemporaryEnvironment()
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
