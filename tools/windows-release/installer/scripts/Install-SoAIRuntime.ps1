[CmdletBinding()]
param(
    [string]$InstallRoot,
    [string]$PythonVersion,
    [string]$PythonUrl,
    [string]$PythonSha256,
    [string]$WebView2BootstrapperUrl = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703',
    [string]$VisualCppRedistUrl = 'https://aka.ms/vc14/vc_redist.x64.exe',
    [string]$StatusPath,
    [string]$DiagnosticRoot,
    [int]$DependencyInstallTimeoutSeconds = 7200,
    [switch]$BootstrapOnly,
    [switch]$PreflightOnly,
    [switch]$VisualCppRuntimeOnly,
    [switch]$SecureAccessOnly,
    [switch]$CompleteInstallation,
    [switch]$ExistingInstallation
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
. (Join-Path $PSScriptRoot 'Shared-SoAIResourceOwnership.ps1')
$ProgressPreference = 'SilentlyContinue'
if ($PreflightOnly -and $BootstrapOnly) {
    throw 'PreflightOnly and BootstrapOnly are mutually exclusive.'
}
if ($VisualCppRuntimeOnly -and ($PreflightOnly -or $BootstrapOnly)) {
    throw 'VisualCppRuntimeOnly cannot be combined with PreflightOnly or BootstrapOnly.'
}
if ($SecureAccessOnly -and ($PreflightOnly -or $BootstrapOnly -or $VisualCppRuntimeOnly -or $ExistingInstallation)) {
    throw 'SecureAccessOnly cannot be combined with other runtime preparation modes.'
}
if ($CompleteInstallation -and !$SecureAccessOnly) {
    throw 'CompleteInstallation requires SecureAccessOnly after runtime dependency installation succeeds.'
}
if ($PreflightOnly -or $BootstrapOnly -or $VisualCppRuntimeOnly -or $SecureAccessOnly) {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    try {
        $principal = [Security.Principal.WindowsPrincipal]::new($identity)
        if (!$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            throw 'Windows runtime preflight, bootstrap, Visual C++ runtime, and file access preparation require an elevated administrator process.'
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
        if ($sourceFields.Count -ne 6 -or @(Compare-Object $sourceFields $expectedFields -CaseSensitive).Count -ne 0 -or
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
# Microsoft requires a Visual C++ runtime at least as new as the newest MSVC toolset used by
# any native dependency; the PyTorch 2.13 Windows wheels are built with 14.44.
$script:MinimumVisualCppRuntimeVersion = [version]'14.44.0.0'
$script:VisualCppRuntimeSourceDirectory = $null
$script:VisualCppRuntimeEvidence = $null
$script:VisualCppRuntimeEvidencePath = $null
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
        [int]$StartupAllowanceSeconds = 0,
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
        $clock = [Diagnostics.Stopwatch]::StartNew()
        $deadlineSeconds = [Math]::Max(60, $TimeoutSeconds)
        $progressDeadlineEnabled = $NoProgressTimeoutSeconds -gt 0
        $progressWatchPaths = @($stdoutLogPath, $stderrLogPath) + @($ProgressPaths)
        $lastProgressFingerprint = Get-ProgressFingerprint -Paths $progressWatchPaths
        $lastProgressSeconds = 0.0
        $inactivityLimitSeconds = $NoProgressTimeoutSeconds
        $startupAllowancePending = $StartupAllowanceSeconds -gt 0
        $nextHeartbeatSeconds = [double]$HeartbeatSeconds
        $nextFingerprintSeconds = 5.0
        $lastActivity = $null
        $lastProgress = $script:InstallProgress
        while (!$process.WaitForExit(1000)) {
            $nowSeconds = $clock.Elapsed.TotalSeconds
            if ($HeartbeatSeconds -gt 0 -and $nowSeconds -ge $nextHeartbeatSeconds) {
                $currentProgress = $script:InstallProgress
                if ($ProgressStart -gt 0 -and $ProgressEnd -gt $ProgressStart) {
                    $expectedSeconds = [Math]::Min([Math]::Max(900, $TimeoutSeconds / 4), 1800)
                    $fraction = [Math]::Min(0.95, [Math]::Max(0.0, $nowSeconds / $expectedSeconds))
                    $currentProgress = $ProgressStart + [int][Math]::Floor(($ProgressEnd - $ProgressStart - 1) * $fraction)
                }
                $activity = Get-CommandActivity -StdoutLogPath $stdoutLogPath -StderrLogPath $stderrLogPath
                if ($activity -cne $lastActivity -or $currentProgress -ne $lastProgress) {
                    Set-InstallProgress -Progress $currentProgress -Detail $activity
                    $lastActivity = $activity
                    $lastProgress = $currentProgress
                }
                $nextHeartbeatSeconds = $nowSeconds + $HeartbeatSeconds
            }
            if ($nowSeconds -gt $deadlineSeconds) {
                $commandState = 'timed-out'
                throw "SoAI $PhaseName did not finish within $TimeoutSeconds seconds."
            }
            if ($progressDeadlineEnabled -and $nowSeconds -ge $nextFingerprintSeconds) {
                $nextFingerprintSeconds = $nowSeconds + 5
                $fingerprint = Get-ProgressFingerprint -Paths $progressWatchPaths
                if ($fingerprint -ne $lastProgressFingerprint) {
                    $lastProgressFingerprint = $fingerprint
                    $lastProgressSeconds = $nowSeconds
                    $inactivityLimitSeconds = $NoProgressTimeoutSeconds
                }
                elseif (($nowSeconds - $lastProgressSeconds) -ge $inactivityLimitSeconds) {
                    if ($startupAllowancePending) {
                        $startupAllowancePending = $false
                        $inactivityLimitSeconds += $StartupAllowanceSeconds
                        Write-InstallerConsoleMessage "[SoAI] $PhaseName is quiet; allowing $StartupAllowanceSeconds more seconds for first-start checks of newly installed runtime files."
                    }
                    else {
                        $commandState = 'stalled'
                        throw "SoAI $PhaseName made no observable progress for $inactivityLimitSeconds seconds."
                    }
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
        [ValidateSet('Exe','Zip','TarGzip')][string]$Kind = 'Exe'
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
    if ($Kind -eq 'TarGzip') {
        $stream = [IO.File]::OpenRead($temp)
        try {
            if ($stream.ReadByte() -ne 0x1f -or $stream.ReadByte() -ne 0x8b) {
                throw 'download did not look like a gzip archive'
            }
        }
        finally { $stream.Dispose() }
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

function Get-CompleteVisualCppRuntimeDllNames {
    return (Get-RequiredVisualCppRuntimeDllNames) + @(
        'concrt140.dll',
        'vcomp140.dll',
        'vcruntime140_threads.dll'
    )
}

function Get-PortableExecutableArchitecture {
    param([Parameter(Mandatory=$true)][string]$Path)
    # Microsoft's ARM64 runtime package contains ARM64EC images that also declare the x64 machine
    # type; only plain x64 images (no CHPE metadata) can be loaded by x64 SoAI processes.
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    try {
        $length = $stream.Length
        $reader = New-Object IO.BinaryReader($stream)
        if ($length -lt 64 -or $reader.ReadUInt16() -ne 0x5A4D) {
            return 'not a Windows DLL'
        }
        [void]$stream.Seek(0x3C, [IO.SeekOrigin]::Begin)
        $headerOffset = [long]$reader.ReadInt32()
        if ($headerOffset -lt 64 -or $headerOffset -gt ($length - 264)) {
            return 'not a Windows DLL'
        }
        [void]$stream.Seek($headerOffset, [IO.SeekOrigin]::Begin)
        if ($reader.ReadUInt32() -ne 0x00004550) {
            return 'not a Windows DLL'
        }
        $machine = [int]$reader.ReadUInt16()
        if ($machine -ne 0x8664) {
            return ('machine 0x{0:X4}' -f $machine)
        }
        $sectionCount = [int]$reader.ReadUInt16()
        [void]$stream.Seek($headerOffset + 20, [IO.SeekOrigin]::Begin)
        $optionalHeaderSize = [int]$reader.ReadUInt16()
        $optionalHeaderOffset = $headerOffset + 24
        [void]$stream.Seek($optionalHeaderOffset, [IO.SeekOrigin]::Begin)
        if ($optionalHeaderSize -lt 200 -or $reader.ReadUInt16() -ne 0x20B) {
            return 'not a 64-bit DLL'
        }
        [void]$stream.Seek($optionalHeaderOffset + 108, [IO.SeekOrigin]::Begin)
        $directoryCount = [long]$reader.ReadUInt32()
        if ($directoryCount -le 10) {
            return 'x64'
        }
        [void]$stream.Seek($optionalHeaderOffset + 192, [IO.SeekOrigin]::Begin)
        $loadConfigRva = [long]$reader.ReadUInt32()
        if ($loadConfigRva -eq 0) {
            return 'x64'
        }
        $sectionTableOffset = $optionalHeaderOffset + $optionalHeaderSize
        if ($sectionTableOffset + (40 * [long]$sectionCount) -gt $length) {
            return 'damaged DLL'
        }
        $loadConfigOffset = $null
        for ($section = 0; $section -lt $sectionCount; $section += 1) {
            [void]$stream.Seek($sectionTableOffset + (40 * $section) + 8, [IO.SeekOrigin]::Begin)
            $virtualSize = [long]$reader.ReadUInt32()
            $virtualAddress = [long]$reader.ReadUInt32()
            $rawSize = [long]$reader.ReadUInt32()
            $rawPointer = [long]$reader.ReadUInt32()
            if ($loadConfigRva -ge $virtualAddress -and $loadConfigRva -lt ($virtualAddress + [Math]::Max($virtualSize, $rawSize))) {
                $loadConfigOffset = $rawPointer + ($loadConfigRva - $virtualAddress)
                break
            }
        }
        if ($null -eq $loadConfigOffset -or $loadConfigOffset + 4 -gt $length) {
            return 'damaged DLL'
        }
        [void]$stream.Seek($loadConfigOffset, [IO.SeekOrigin]::Begin)
        $loadConfigSize = [long]$reader.ReadUInt32()
        if ($loadConfigSize -lt 0xD0) {
            return 'x64'
        }
        if ($loadConfigOffset + 0xD0 -gt $length) {
            return 'damaged DLL'
        }
        [void]$stream.Seek($loadConfigOffset + 0xC8, [IO.SeekOrigin]::Begin)
        if ($reader.ReadUInt64() -ne 0) {
            return 'ARM64EC'
        }
        return 'x64'
    }
    finally {
        $stream.Dispose()
    }
}

function Get-VisualCppRuntimeFileState {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Name
    )
    $version = $null
    $architecture = $null
    $problem = $null
    if (![IO.File]::Exists($Path)) {
        $problem = 'missing'
    }
    else {
        try {
            $info = [Diagnostics.FileVersionInfo]::GetVersionInfo($Path)
            $version = New-Object Version($info.FileMajorPart, $info.FileMinorPart, $info.FileBuildPart, $info.FilePrivatePart)
            $architecture = Get-PortableExecutableArchitecture -Path $Path
            if ($architecture -ne 'x64') {
                $problem = "not an x64 DLL: $architecture"
            }
            elseif ($version -lt $script:MinimumVisualCppRuntimeVersion) {
                $problem = "older than $script:MinimumVisualCppRuntimeVersion"
            }
        }
        catch {
            $version = $null
            $architecture = $null
            $problem = "unreadable: $($_.Exception.Message)"
        }
    }
    return [pscustomobject]@{
        Name = $Name
        Path = $Path
        Version = $version
        Architecture = $architecture
        Problem = $problem
    }
}

function Get-VisualCppRuntimeDirectoryState {
    param(
        [Parameter(Mandatory=$true)][string]$Directory,
        [Parameter(Mandatory=$true)][string[]]$DllNames
    )
    $files = @(foreach ($dllName in $DllNames) {
        Get-VisualCppRuntimeFileState -Path (Join-Path $Directory $dllName) -Name $dllName
    })
    $problems = @($files | Where-Object { $null -ne $_.Problem } | ForEach-Object { "$($_.Name) ($($_.Problem))" })
    return [pscustomobject]@{
        Directory = $Directory
        Files = $files
        Problems = $problems
        Ready = $problems.Count -eq 0
    }
}

function ConvertTo-VisualCppRuntimeEvidence {
    param([Parameter(Mandatory=$true)][object]$State)
    $files = [ordered]@{}
    foreach ($file in $State.Files) {
        $versionText = $null
        if ($null -ne $file.Version) {
            $versionText = $file.Version.ToString()
        }
        $files[$file.Name] = [ordered]@{
            version = $versionText
            architecture = $file.Architecture
            problem = $file.Problem
        }
    }
    return [ordered]@{
        directory = $State.Directory
        ready = $State.Ready
        files = $files
    }
}

function Format-VisualCppRuntimeProblems {
    param([Parameter(Mandatory=$true)][object]$State)
    $details = @(foreach ($file in $State.Files) {
        if ($null -eq $file.Problem) {
            continue
        }
        if ($null -ne $file.Version) {
            "$($file.Name) $($file.Version) ($($file.Problem))"
        }
        else {
            "$($file.Name) ($($file.Problem))"
        }
    })
    return $details -join ', '
}

function Get-UniqueInstallLogPath {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$Extension
    )
    $logDir = Get-InstallLogDir -Root $Root
    for ($attempt = 1; $attempt -le 10000; $attempt += 1) {
        $suffix = ''
        if ($attempt -gt 1) {
            $suffix = ".attempt-$attempt"
        }
        $path = Join-Path $logDir "$Name$suffix$Extension"
        if (!(Test-Path -LiteralPath $path)) {
            return $path
        }
    }
    throw "Could not allocate a diagnostic log for installer phase: $Name"
}

function Add-VisualCppRuntimeEvidence {
    param([Parameter(Mandatory=$true)][System.Collections.IDictionary]$Entry)
    $Entry['at_utc'] = [DateTime]::UtcNow.ToString('o')
    [void]$script:VisualCppRuntimeEvidence['events'].Add($Entry)
}

function Save-VisualCppRuntimeEvidence {
    if ($null -eq $script:VisualCppRuntimeEvidence) {
        return
    }
    try {
        $script:VisualCppRuntimeEvidence['updated_at_utc'] = [DateTime]::UtcNow.ToString('o')
        $script:VisualCppRuntimeEvidence | ConvertTo-Json -Depth 8 |
            Set-Content -LiteralPath $script:VisualCppRuntimeEvidencePath -Encoding UTF8 -ErrorAction Stop
    }
    catch {
        Write-Warning "Microsoft Visual C++ runtime diagnostics could not be saved: $($_.Exception.Message)"
    }
}

function Initialize-VisualCppRuntimeEvidence {
    param([Parameter(Mandatory=$true)][string]$Root)
    if ($null -ne $script:VisualCppRuntimeEvidence) {
        return
    }
    $script:VisualCppRuntimeEvidencePath = Get-UniqueInstallLogPath -Root $Root -Name 'visual-cpp-runtime' -Extension '.json'
    $script:VisualCppRuntimeEvidence = [ordered]@{
        schema_version = 1
        started_at_utc = [DateTime]::UtcNow.ToString('o')
        windows_version = [Environment]::OSVersion.VersionString
        process_architecture = $env:PROCESSOR_ARCHITECTURE
        minimum_version = $script:MinimumVisualCppRuntimeVersion.ToString()
        registry_version = Get-VisualCppRuntimeVersion
        redistributable_url = $VisualCppRedistUrl
        source = $null
        events = New-Object System.Collections.ArrayList
    }
}

function Invoke-VisualCppRuntimeProcess {
    param(
        [Parameter(Mandatory=$true)][string]$Executable,
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [Parameter(Mandatory=$true)][int]$TimeoutSeconds
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Executable
    $psi.Arguments = Join-ProcessArguments $Arguments
    $psi.WorkingDirectory = [Environment]::GetFolderPath('System')
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $process = [System.Diagnostics.Process]::Start($psi)
    try {
        if (!$process.WaitForExit($TimeoutSeconds * 1000)) {
            try {
                $process.Kill()
            }
            catch {
            }
            return $null
        }
        return $process.ExitCode
    }
    finally {
        $process.Dispose()
    }
}

function Invoke-VisualCppRedistributable {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$Redistributable,
        [Parameter(Mandatory=$true)][ValidateSet('install', 'repair')][string]$Operation
    )
    $exitCode = $null
    $timeoutSeconds = ([SoAILauncher.NativeImageBudget]::Calculate(1200, [string[]]@($Redistributable), [string[]]@(), [string[]]@(),
        @(Get-CompleteVisualCppRuntimeDllNames).Count)).WholeSeconds
    $timeoutMinutes = [int][Math]::Ceiling($timeoutSeconds / 60)
    for ($attempt = 1; $attempt -le 6; $attempt += 1) {
        $logPath = Get-UniqueInstallLogPath -Root $Root -Name "visual-cpp-redist-$Operation" -Extension '.log'
        $exitCode = Invoke-VisualCppRuntimeProcess -Executable $Redistributable `
            -Arguments @("/$Operation", '/quiet', '/norestart', '/log', $logPath) -TimeoutSeconds $timeoutSeconds
        Add-VisualCppRuntimeEvidence ([ordered]@{
            action = "redistributable-$Operation"
            attempt = $attempt
            exit_code = $exitCode
            timed_out = $null -eq $exitCode
            log = $logPath
        })
        if ($null -eq $exitCode) {
            Write-InstallerConsoleMessage "[SoAI] Microsoft Visual C++ Runtime $Operation did not finish within $timeoutMinutes minutes. Log: $logPath"
            return $null
        }
        Write-InstallerConsoleMessage "[SoAI] Microsoft Visual C++ Runtime $Operation finished with exit code $exitCode. Log: $logPath"
        if ($exitCode -ne 1618 -or $attempt -eq 6) {
            return $exitCode
        }
        Write-Step 'Another Windows installation is running; retrying the Microsoft Visual C++ Runtime shortly...'
        Start-Sleep -Seconds 30
    }
    return $exitCode
}

function Copy-VisualCppRuntimeSnapshot {
    param(
        [Parameter(Mandatory=$true)][string]$SourceDirectory,
        [Parameter(Mandatory=$true)][string]$Destination
    )
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    foreach ($dllName in Get-CompleteVisualCppRuntimeDllNames) {
        Copy-Item -LiteralPath (Join-Path $SourceDirectory $dllName) -Destination (Join-Path $Destination $dllName) -Force
    }
}

function Expand-VisualCppRuntimeRedistributable {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$Redistributable,
        [Parameter(Mandatory=$true)][string]$Destination
    )
    $layoutDir = Join-Path $script:InstallerDownloadRoot 'vc-redist-layout'
    $cabinetDir = Join-Path $script:InstallerDownloadRoot 'vc-redist-cabinets'
    foreach ($directory in @($layoutDir, $cabinetDir)) {
        if (Test-Path -LiteralPath $directory) {
            Remove-Item -LiteralPath $directory -Recurse -Force
        }
        New-Item -ItemType Directory -Force -Path $directory | Out-Null
    }
    $logPath = Get-UniqueInstallLogPath -Root $Root -Name 'visual-cpp-redist-layout' -Extension '.log'
    $timeoutSeconds = ([SoAILauncher.NativeImageBudget]::Calculate(1200, [string[]]@($Redistributable), [string[]]@(), [string[]]@(), 0)).WholeSeconds
    $exitCode = Invoke-VisualCppRuntimeProcess -Executable $Redistributable `
        -Arguments @('/layout', $layoutDir, '/quiet', '/norestart', '/log', $logPath) -TimeoutSeconds $timeoutSeconds
    Add-VisualCppRuntimeEvidence ([ordered]@{
        action = 'redistributable-layout'
        exit_code = $exitCode
        timed_out = $null -eq $exitCode
        log = $logPath
    })
    if ($null -eq $exitCode) {
        throw "The Microsoft Visual C++ Redistributable layout did not finish within $([int][Math]::Ceiling($timeoutSeconds / 60)) minutes. Log: $logPath"
    }
    if ($exitCode -ne 0) {
        throw "The Microsoft Visual C++ Redistributable layout failed with exit code $exitCode. Log: $logPath"
    }
    $cabinets = @(Get-ChildItem -LiteralPath $layoutDir -Recurse -File -Filter '*.cab' | Sort-Object FullName)
    if ($cabinets.Count -eq 0) {
        throw "The Microsoft Visual C++ Redistributable layout contained no runtime cabinets. Log: $logPath"
    }
    $expand = Join-Path $env:WINDIR 'System32\expand.exe'
    for ($index = 0; $index -lt $cabinets.Count; $index += 1) {
        $cabinetTarget = Join-Path $cabinetDir ('{0:D2}' -f ($index + 1))
        New-Item -ItemType Directory -Force -Path $cabinetTarget | Out-Null
        Invoke-LoggedCommand -Root $Root -PhaseName 'expand-visual-cpp-runtime' `
            -WorkingDirectory $cabinetTarget -Executable $expand `
            -Arguments @($cabinets[$index].FullName, '-F:*', $cabinetTarget) `
            -EnvironmentValues @{} -TimeoutSeconds 600 | Out-Null
    }

    $requiredNames = @(Get-CompleteVisualCppRuntimeDllNames)
    $candidates = @{}
    foreach ($file in @(Get-ChildItem -LiteralPath $cabinetDir -Recurse -File | Sort-Object FullName)) {
        $originalName = [string]([Diagnostics.FileVersionInfo]::GetVersionInfo($file.FullName).OriginalFilename)
        $requiredName = $requiredNames | Where-Object { [string]::Equals($_, $originalName.Trim(), [StringComparison]::OrdinalIgnoreCase) } | Select-Object -First 1
        if ($null -eq $requiredName) {
            continue
        }
        $state = Get-VisualCppRuntimeFileState -Path $file.FullName -Name $requiredName
        if ($null -ne $state.Problem) {
            continue
        }
        if (!$candidates.ContainsKey($requiredName) -or $state.Version -gt $candidates[$requiredName].Version) {
            $candidates[$requiredName] = $state
        }
    }

    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    foreach ($requiredName in $requiredNames) {
        if (!$candidates.ContainsKey($requiredName)) {
            throw "The Microsoft Visual C++ Redistributable did not contain a usable x64 $requiredName at version $script:MinimumVisualCppRuntimeVersion or newer. Diagnostics: $script:VisualCppRuntimeEvidencePath"
        }
        $candidate = $candidates[$requiredName]
        Assert-AuthenticodeValid -Path $candidate.Path -ExpectedPublisher 'Microsoft'
        Copy-Item -LiteralPath $candidate.Path -Destination (Join-Path $Destination $requiredName) -Force
    }
}

function Resolve-VisualCppRuntimeSource {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [string[]]$ReadySoAIRuntimeDirectories = @()
    )
    $system32 = Join-Path $env:WINDIR 'System32'
    $staging = Join-Path $script:InstallerDownloadRoot 'visual-cpp-runtime'
    $systemState = Get-VisualCppRuntimeDirectoryState -Directory $system32 -DllNames (Get-CompleteVisualCppRuntimeDllNames)
    Add-VisualCppRuntimeEvidence ([ordered]@{
        action = 'inspect-windows-runtime'
        state = ConvertTo-VisualCppRuntimeEvidence $systemState
    })
    if ($systemState.Ready) {
        Copy-VisualCppRuntimeSnapshot -SourceDirectory $system32 -Destination $staging
        $script:VisualCppRuntimeEvidence['source'] = 'windows'
        return $staging
    }

    Write-InstallerConsoleMessage "[SoAI] The Microsoft Visual C++ runtime installed in Windows is not usable by SoAI: $(Format-VisualCppRuntimeProblems $systemState)."
    # A complete runtime set that an earlier SoAI installation already verified is reused, so a
    # machine whose Windows runtime cannot be repaired does not download it on every update.
    foreach ($readyDirectory in $ReadySoAIRuntimeDirectories) {
        Copy-VisualCppRuntimeSnapshot -SourceDirectory $readyDirectory -Destination $staging
        $script:VisualCppRuntimeEvidence['source'] = 'soai-runtime'
        $script:VisualCppRuntimeEvidence['source_directory'] = $readyDirectory
        return $staging
    }
    $redistributable = Join-Path $script:InstallerDownloadRoot 'vc_redist.x64.exe'
    Download-File -Uri $VisualCppRedistUrl -Destination $redistributable
    Assert-AuthenticodeValid -Path $redistributable -ExpectedPublisher 'Microsoft'
    $script:VisualCppRuntimeEvidence['redistributable_version'] = [Diagnostics.FileVersionInfo]::GetVersionInfo($redistributable).FileVersion

    Write-Step 'Installing Microsoft Visual C++ Runtime...'
    $exitCode = Invoke-VisualCppRedistributable -Root $Root -Redistributable $redistributable -Operation 'install'
    $systemState = Get-VisualCppRuntimeDirectoryState -Directory $system32 -DllNames (Get-CompleteVisualCppRuntimeDllNames)
    if (!$systemState.Ready -and $null -ne $exitCode -and $exitCode -notin @(1618, 1641, 3010)) {
        Write-Step 'Repairing Microsoft Visual C++ Runtime...'
        [void](Invoke-VisualCppRedistributable -Root $Root -Redistributable $redistributable -Operation 'repair')
        $systemState = Get-VisualCppRuntimeDirectoryState -Directory $system32 -DllNames (Get-CompleteVisualCppRuntimeDllNames)
    }
    Add-VisualCppRuntimeEvidence ([ordered]@{
        action = 'inspect-windows-runtime'
        state = ConvertTo-VisualCppRuntimeEvidence $systemState
    })
    if ($systemState.Ready) {
        Write-Step 'Microsoft Visual C++ Runtime is updated.'
        Copy-VisualCppRuntimeSnapshot -SourceDirectory $system32 -Destination $staging
        $script:VisualCppRuntimeEvidence['source'] = 'windows'
        return $staging
    }

    Write-InstallerConsoleMessage "[SoAI] Windows still reports an unusable Visual C++ runtime after setup (a restart may be pending): $(Format-VisualCppRuntimeProblems $systemState)."
    Write-Step 'Preparing a verified private Microsoft Visual C++ runtime for SoAI...'
    Expand-VisualCppRuntimeRedistributable -Root $Root -Redistributable $redistributable -Destination $staging
    $script:VisualCppRuntimeEvidence['source'] = 'redistributable-extraction'
    return $staging
}

function Update-RuntimeDllFile {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination
    )
    $temporary = "$Destination.$([Guid]::NewGuid().ToString('N')).tmp"
    try {
        Copy-Item -LiteralPath $Source -Destination $temporary -Force
        if ([IO.File]::Exists($Destination)) {
            $attributes = [IO.File]::GetAttributes($Destination)
            if (($attributes -band [IO.FileAttributes]::ReadOnly) -ne 0) {
                [IO.File]::SetAttributes($Destination, ($attributes -band (-bnot [IO.FileAttributes]::ReadOnly)))
            }
        }
        Move-Item -LiteralPath $temporary -Destination $Destination -Force
    }
    catch {
        $failure = $_.Exception.Message
        Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
        throw "SoAI could not update $Destination. If SoAI is running, stop it and run the installation again. $failure"
    }
}

function Get-ManagedVenvHome {
    param([Parameter(Mandatory=$true)][string]$Root)
    $configPath = Join-Path $Root 'soai_main_venv\pyvenv.cfg'
    if (!(Test-Path -LiteralPath $configPath -PathType Leaf)) {
        return $null
    }
    foreach ($line in [IO.File]::ReadAllLines($configPath)) {
        $match = [regex]::Match($line, '^\s*home\s*=\s*(.+?)\s*$')
        if (!$match.Success) {
            continue
        }
        try {
            $homeDirectory = [IO.Path]::GetFullPath([SoAILauncher.LauncherPaths]::RemoveWindowsPathNamespace($match.Groups[1].Value)).TrimEnd('\')
            $rootDirectory = [IO.Path]::GetFullPath([SoAILauncher.LauncherPaths]::RemoveWindowsPathNamespace($Root)).TrimEnd('\')
        }
        catch {
            return $null
        }
        if (!$homeDirectory.StartsWith($rootDirectory + '\', [StringComparison]::OrdinalIgnoreCase)) {
            Write-InstallerConsoleMessage "[SoAI] The SoAI managed environment uses a Python outside the SoAI installation; SoAI will not modify it: $homeDirectory"
            return $null
        }
        return $homeDirectory
    }
    return $null
}

function Install-VisualCppRuntime {
    param([Parameter(Mandatory=$true)][string]$Root)
    Copy-AppLocalVisualCppRuntimeDlls -Root $Root
    $sourceDescription = 'existing SoAI copy'
    if ($script:VisualCppRuntimeEvidence['source'] -eq 'windows') {
        $sourceDescription = 'Windows'
    }
    elseif ($script:VisualCppRuntimeEvidence['source'] -eq 'redistributable-extraction') {
        $sourceDescription = 'verified private copy'
    }
    Write-Step "Microsoft Visual C++ runtime for SoAI is ready ($sourceDescription)."
}

function Copy-AppLocalVisualCppRuntimeDlls {
    param([Parameter(Mandatory=$true)][string]$Root)
    Initialize-VisualCppRuntimeEvidence -Root $Root
    $rootDir = (Resolve-FullPath $Root).TrimEnd('\')
    $targets = New-Object System.Collections.Generic.List[object]
    $targetDirectories = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    [void]$targetDirectories.Add($rootDir)
    [void]$targets.Add([pscustomobject]@{ Directory = $rootDir; DllNames = @(Get-RequiredVisualCppRuntimeDllNames) })
    $pythonDir = Resolve-ChildPath -Root $Root -Child 'python'
    $interpreterDirs = @($pythonDir) + @(foreach ($legacyDir in @('python-3.13', 'runtime\python', 'runtime\python-3.13', 'soai_python')) {
        Resolve-ChildPath -Root $Root -Child $legacyDir
    })
    $venvHome = Get-ManagedVenvHome -Root $rootDir
    if ($null -ne $venvHome) {
        $interpreterDirs += $venvHome
    }
    foreach ($interpreterDir in $interpreterDirs) {
        if ((Test-Path -LiteralPath (Join-Path $interpreterDir 'python.exe') -PathType Leaf) -and $targetDirectories.Add($interpreterDir)) {
            [void]$targets.Add([pscustomobject]@{ Directory = $interpreterDir; DllNames = @(Get-CompleteVisualCppRuntimeDllNames) })
        }
    }
    $venvScripts = Resolve-ChildPath -Root $Root -Child 'soai_main_venv\Scripts'
    if ((Test-Path -LiteralPath $venvScripts -PathType Container) -and $targetDirectories.Add($venvScripts)) {
        [void]$targets.Add([pscustomobject]@{ Directory = $venvScripts; DllNames = @(Get-CompleteVisualCppRuntimeDllNames) })
    }

    try {
        $completeDllCount = @(Get-CompleteVisualCppRuntimeDllNames).Count
        $readySoAIRuntimeDirectories = New-Object System.Collections.Generic.List[string]
        $pendingTargets = @(foreach ($target in $targets) {
            $state = Get-VisualCppRuntimeDirectoryState -Directory $target.Directory -DllNames $target.DllNames
            Add-VisualCppRuntimeEvidence ([ordered]@{
                action = 'inspect-soai-runtime'
                state = ConvertTo-VisualCppRuntimeEvidence $state
            })
            if (!$state.Ready) {
                $target
            }
            elseif ($target.DllNames.Count -eq $completeDllCount) {
                [void]$readySoAIRuntimeDirectories.Add($target.Directory)
            }
        })
        if ($pendingTargets.Count -eq 0) {
            return
        }

        $sourceDir = $script:VisualCppRuntimeSourceDirectory
        if ($null -eq $sourceDir) {
            $sourceDir = Resolve-VisualCppRuntimeSource -Root $Root -ReadySoAIRuntimeDirectories $readySoAIRuntimeDirectories.ToArray()
            $sourceState = Get-VisualCppRuntimeDirectoryState -Directory $sourceDir -DllNames (Get-CompleteVisualCppRuntimeDllNames)
            if (!$sourceState.Ready) {
                throw "The selected Microsoft Visual C++ runtime is not usable: $(Format-VisualCppRuntimeProblems $sourceState). Diagnostics: $script:VisualCppRuntimeEvidencePath"
            }
            $script:VisualCppRuntimeSourceDirectory = $sourceDir
        }

        foreach ($target in $pendingTargets) {
            # A directory that needs repair receives the complete verified source set so its
            # runtime DLLs stay one coherent Microsoft release; ready directories are never touched.
            foreach ($dllName in $target.DllNames) {
                $sourceState = Get-VisualCppRuntimeFileState -Path (Join-Path $sourceDir $dllName) -Name $dllName
                $targetState = Get-VisualCppRuntimeFileState -Path (Join-Path $target.Directory $dllName) -Name $dllName
                if ($null -eq $targetState.Problem -and $targetState.Version -eq $sourceState.Version) {
                    continue
                }
                Update-RuntimeDllFile -Source $sourceState.Path -Destination $targetState.Path
            }
            $state = Get-VisualCppRuntimeDirectoryState -Directory $target.Directory -DllNames $target.DllNames
            Add-VisualCppRuntimeEvidence ([ordered]@{
                action = 'update-soai-runtime'
                state = ConvertTo-VisualCppRuntimeEvidence $state
            })
            if (!$state.Ready) {
                throw "SoAI could not prepare the Microsoft Visual C++ runtime in $($target.Directory): $(Format-VisualCppRuntimeProblems $state). Diagnostics: $script:VisualCppRuntimeEvidencePath"
            }
        }
    }
    catch {
        Add-VisualCppRuntimeEvidence ([ordered]@{
            action = 'failure'
            message = $_.Exception.Message
        })
        throw
    }
    finally {
        Save-VisualCppRuntimeEvidence
    }
}

function Get-PythonProbeTimeoutSeconds {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$PythonExe,
        [Parameter(Mandatory=$true)][int]$OrdinarySeconds
    )
    $pythonHome = Resolve-ChildPath -Root $Root -Child 'python'
    $allowance = [SoAILauncher.NativeImageBudget]::Calculate($OrdinarySeconds,
        [string[]]@($PythonExe, (Join-Path $pythonHome 'DLLs')),
        [string[]]@((Split-Path -Parent $PythonExe), $pythonHome), [string[]]@(), 0)
    return $allowance.WholeSeconds
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
            -Arguments @('--version') -EnvironmentValues @{} `
            -TimeoutSeconds (Get-PythonProbeTimeoutSeconds -Root $Root -PythonExe $PythonExe -OrdinarySeconds 60)
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

function Get-PythonRuntimeArchiveSuffix {
    if (([Uri]$PythonUrl).AbsolutePath.EndsWith('.tar.gz', [StringComparison]::Ordinal)) {
        return 'tar.gz'
    }
    return 'nupkg'
}

function Read-PythonArchiveBytes {
    param(
        [Parameter(Mandatory=$true)][IO.Stream]$Stream,
        [Parameter(Mandatory=$true)][byte[]]$Buffer,
        [Parameter(Mandatory=$true)][int]$Count
    )
    $offset = 0
    while ($offset -lt $Count) {
        $received = $Stream.Read($Buffer, $offset, $Count - $offset)
        if ($received -eq 0) { throw 'The Python runtime archive ended before its content was complete.' }
        $offset += $received
    }
}

function Get-PythonArchiveOctal {
    param(
        [Parameter(Mandatory=$true)][byte[]]$Header,
        [Parameter(Mandatory=$true)][int]$Offset,
        [Parameter(Mandatory=$true)][int]$Length
    )
    $text = [Text.Encoding]::ASCII.GetString($Header, $Offset, $Length).Trim([char[]]@(0, 32))
    if ($text -notmatch '^[0-7]{1,11}$') { throw 'The Python runtime archive contains an invalid numeric field.' }
    return [Convert]::ToInt64($text, 8)
}

function Get-PythonArchiveTextField {
    param(
        [Parameter(Mandatory=$true)][byte[]]$Header,
        [Parameter(Mandatory=$true)][int]$Offset,
        [Parameter(Mandatory=$true)][int]$Length,
        [Parameter(Mandatory=$true)][Text.Encoding]$Encoding
    )
    $terminator = [Array]::IndexOf($Header, [byte]0, $Offset, $Length)
    if ($terminator -ge 0) { $Length = $terminator - $Offset }
    return $Encoding.GetString($Header, $Offset, $Length)
}

function Expand-PythonRuntimeTar {
    param(
        [Parameter(Mandatory=$true)][string]$Archive,
        [Parameter(Mandatory=$true)][string]$Destination
    )
    $nativeDestination = Resolve-NativePath $Destination
    [IO.Directory]::CreateDirectory($nativeDestination) | Out-Null
    if (@([IO.Directory]::EnumerateFileSystemEntries($nativeDestination)).Count -ne 0) {
        throw 'Python runtime extraction requires an empty staging directory.'
    }
    $destinationPrefix = $nativeDestination.TrimEnd('\') + '\'
    $names = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $encoding = [Text.UTF8Encoding]::new($false, $true)
    $header = New-Object byte[] 512
    $buffer = New-Object byte[] 65536
    $totalBytes = 0L
    $deadline = [Diagnostics.Stopwatch]::StartNew()
    $archiveStream = [IO.File]::OpenRead((Resolve-NativePath $Archive))
    try {
        $gzip = [IO.Compression.GZipStream]::new($archiveStream, [IO.Compression.CompressionMode]::Decompress)
        try {
            while ($true) {
                if ($deadline.Elapsed.TotalMinutes -ge 30) { throw 'Python runtime extraction exceeded its 30-minute deadline.' }
                Read-PythonArchiveBytes -Stream $gzip -Buffer $header -Count 512
                $nonzero = $false
                foreach ($value in $header) { if ($value -ne 0) { $nonzero = $true; break } }
                if (!$nonzero) {
                    Read-PythonArchiveBytes -Stream $gzip -Buffer $header -Count 512
                    foreach ($value in $header) { if ($value -ne 0) { throw 'The Python runtime archive has an invalid end marker.' } }
                    $trailingBytes = 0
                    while (($received = $gzip.Read($buffer, 0, $buffer.Length)) -gt 0) {
                        $trailingBytes += $received
                        if ($trailingBytes -gt 1MB) { throw 'The Python runtime archive has excessive trailing data.' }
                        for ($offset = 0; $offset -lt $received; $offset++) {
                            if ($buffer[$offset] -ne 0) { throw 'The Python runtime archive has unexpected trailing content.' }
                        }
                    }
                    if ($names.Count -eq 0) { throw 'The Python runtime archive contains no files.' }
                    return
                }
                $storedChecksum = Get-PythonArchiveOctal -Header $header -Offset 148 -Length 8
                $checksum = 0L
                for ($offset = 0; $offset -lt 512; $offset++) {
                    if ($offset -ge 148 -and $offset -lt 156) { $checksum += 32 }
                    else { $checksum += $header[$offset] }
                }
                if ($checksum -ne $storedChecksum -or $header[156] -notin @(0, 48) -or
                    $encoding.GetString($header, 257, 5) -cne 'ustar') {
                    throw 'The Python runtime archive contains an invalid header or unsupported file type.'
                }
                $name = Get-PythonArchiveTextField -Header $header -Offset 0 -Length 100 -Encoding $encoding
                $prefix = Get-PythonArchiveTextField -Header $header -Offset 345 -Length 155 -Encoding $encoding
                if ($prefix.Length -gt 0) { $name = $prefix + '/' + $name }
                if (!$name.StartsWith('python/', [StringComparison]::Ordinal)) {
                    throw 'The Python runtime archive contains a file outside its python directory.'
                }
                foreach ($segment in $name.Split('/')) {
                    if ([string]::IsNullOrEmpty($segment) -or $segment -in @('.', '..') -or
                        $segment.IndexOfAny([IO.Path]::GetInvalidFileNameChars()) -ge 0 -or
                        $segment.EndsWith('.') -or $segment.EndsWith(' ') -or
                        $segment -match '^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$') {
                        throw 'The Python runtime archive contains an unsafe filename.'
                    }
                }
                $target = Resolve-NativePath ([IO.Path]::Combine($Destination,
                    $name.Replace([char]'/', [IO.Path]::DirectorySeparatorChar)))
                if (!$target.StartsWith($destinationPrefix, [StringComparison]::OrdinalIgnoreCase) -or
                    !$names.Add($target) -or $names.Count -gt 20000) {
                    throw 'The Python runtime archive contains conflicting paths or too many files.'
                }
                $size = Get-PythonArchiveOctal -Header $header -Offset 124 -Length 12
                $totalBytes += $size
                if ($totalBytes -gt 256MB) { throw 'The Python runtime archive exceeds its extracted size limit.' }
                [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($target)) | Out-Null
                $output = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
                try {
                    $remaining = $size
                    while ($remaining -gt 0) {
                        if ($deadline.Elapsed.TotalMinutes -ge 30) { throw 'Python runtime extraction exceeded its 30-minute deadline.' }
                        $count = [int][Math]::Min($remaining, $buffer.Length)
                        Read-PythonArchiveBytes -Stream $gzip -Buffer $buffer -Count $count
                        $output.Write($buffer, 0, $count)
                        $remaining -= $count
                    }
                    $output.Flush($true)
                }
                finally { $output.Dispose() }
                $padding = [int]((512 - ($size % 512)) % 512)
                if ($padding -gt 0) { Read-PythonArchiveBytes -Stream $gzip -Buffer $buffer -Count $padding }
            }
        }
        finally { $gzip.Dispose() }
    }
    finally { $archiveStream.Dispose() }
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
    $suffix = Get-PythonRuntimeArchiveSuffix
    $archivePath = Join-Path $platformDirectory "python-$PythonVersion.$suffix"
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
        $sourceState = Get-VisualCppRuntimeFileState -Path (Join-Path $pythonDir $dllName) -Name $dllName
        if ($null -eq $sourceState.Version -or $sourceState.Architecture -ne 'x64') {
            continue
        }
        foreach ($target in $targets) {
            # Never replace a newer runtime DLL with the older copy bundled with Python.
            $targetState = Get-VisualCppRuntimeFileState -Path (Join-Path $target $dllName) -Name $dllName
            if ($targetState.Architecture -eq 'x64' -and $targetState.Version -ge $sourceState.Version) {
                continue
            }
            Update-RuntimeDllFile -Source $sourceState.Path -Destination $targetState.Path
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
    $suffix = Get-PythonRuntimeArchiveSuffix
    $package = Join-Path $downloadDir "python-$PythonVersion.$suffix"
    $packageZip = Join-Path $downloadDir "python-$PythonVersion.zip"
    $extractDir = Join-Path $downloadDir "python-$PythonVersion-package"
    New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
    $packagedRuntime = Get-PackagedPythonRuntimePath -Root $Root
    if ($null -ne $packagedRuntime) {
        Copy-Item -LiteralPath $packagedRuntime -Destination $package -Force
        Assert-Hash -Path $package -Sha256 $PythonSha256
    }
    elseif (!(Test-Path -LiteralPath $package)) {
        $archiveType = if ($suffix -eq 'tar.gz') { 'TarGzip' } else { 'Zip' }
        Download-File -Uri $PythonUrl -Destination $package -Sha256 $PythonSha256 -Kind $archiveType
    }
    else {
        Assert-Hash -Path $package -Sha256 $PythonSha256
    }

    Write-Step "Extracting app-local Python $PythonVersion runtime..."
    Remove-Item -LiteralPath $extractDir -Recurse -Force -ErrorAction SilentlyContinue
    if ($suffix -eq 'tar.gz') {
        Expand-PythonRuntimeTar -Archive $package -Destination $extractDir
        $toolsDir = Join-Path $extractDir 'python'
    }
    else {
        Copy-Item -LiteralPath $package -Destination $packageZip -Force
        Expand-Archive -LiteralPath $packageZip -DestinationPath $extractDir -Force
        $toolsDir = Join-Path $extractDir 'tools'
    }
    if (!(Test-Path -LiteralPath (Join-Path $toolsDir 'python.exe'))) {
        throw 'The Python package did not contain its required python.exe.'
    }
    [void](Test-PythonRuntime -Root $Root -PythonExe (Join-Path $toolsDir 'python.exe') -Required)
    if (Test-Path -LiteralPath $pythonDir) {
        Write-Step 'Replacing the previous Python runtime...'
        Remove-Item -LiteralPath $pythonDir -Recurse -Force
    }
    $toolsMove = [SoAILauncher.SharingConflictWait]::Begin($toolsDir, $pythonDir)
    try {
        while ($true) {
            try {
                Move-Item -LiteralPath $toolsDir -Destination $pythonDir -Force -ErrorAction Stop
                break
            }
            catch {
                if (!$toolsMove.ShouldRetry($_.Exception)) { throw }
            }
        }
    }
    finally { $toolsMove.Dispose() }
    [void](Test-PythonRuntime -Root $Root -PythonExe $pythonExe -Required)
    Copy-AppLocalPythonRuntimeDlls -Root $Root
}

function Install-Stage0BootstrapDependencies {
    param([Parameter(Mandatory=$true)][string]$Root)
    $pythonExe = Resolve-ChildPath -Root $Root -Child 'python\python.exe'
    $runtimeRequirementsPath = Resolve-ChildPath -Root $Root -Child 'requirements.txt'
    if (![IO.File]::Exists($runtimeRequirementsPath)) {
        throw 'SoAI runtime requirements are missing. Reinstall SoAI from a verified package.'
    }
    $runtimeRequirements = [IO.File]::ReadAllLines($runtimeRequirementsPath)
    $stage0Requirements = @(
        foreach ($package in @('ruamel-yaml', 'httpx2', 'filelock', 'psutil')) {
            $pattern = '^' + [regex]::Escape($package) + '==[^\s;]+$'
            $matchingRequirements = @($runtimeRequirements | Where-Object { $_ -match $pattern })
            if ($matchingRequirements.Count -ne 1) {
                throw "SoAI requires one unconditional runtime pin for ${package}. Reinstall SoAI from a verified package."
            }
            $matchingRequirements[0]
        }
    )
    Write-Step 'Preparing the SoAI stage-0 bootstrap dependencies...'
    $tlsBootstrapRequirements = Resolve-ChildPath -Root $Root -Child 'backend\core\bootstrap\tls_bootstrap_requirements.txt'
    Invoke-LoggedCommand -Root $Root -PhaseName 'install-stage0-pip' `
        -WorkingDirectory ([Environment]::GetFolderPath('System')) -Executable $pythonExe `
        -Arguments @('-m', 'pip', 'install', '--disable-pip-version-check', '--no-warn-script-location',
            '--upgrade', '--force-reinstall', '--no-deps', '--only-binary=:all:', '--require-hashes',
            '-r', $tlsBootstrapRequirements) `
        -EnvironmentValues @{ PYTHONUTF8 = '1'; PYTHONIOENCODING = 'utf-8' } `
        -TimeoutSeconds $DependencyInstallTimeoutSeconds -HeartbeatSeconds 2 `
        -HeartbeatMessage 'Updating Python package installer certificates' | Out-Null
    Invoke-LoggedCommand -Root $Root -PhaseName 'install-stage0-dependencies' `
        -WorkingDirectory ([Environment]::GetFolderPath('System')) -Executable $pythonExe `
        -Arguments (@('-m', 'pip', 'install', '--disable-pip-version-check', '--no-warn-script-location', '--upgrade') + $stage0Requirements) `
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
    $timeoutSeconds = ([SoAILauncher.NativeImageBudget]::Calculate(600, [string[]]@($bootstrapper), [string[]]@(), [string[]]@(), 0)).WholeSeconds
    $process = Start-Process -FilePath $bootstrapper -ArgumentList @('/silent', '/install') -PassThru
    if (!$process.WaitForExit($timeoutSeconds * 1000)) {
        try {
            $process.Kill()
        }
        catch {
        }
        throw "WebView2 Runtime installer did not finish within $([int][Math]::Ceiling($timeoutSeconds / 60)) minutes."
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
    $failedInstallPhase = $script:LastFailedInstallPhase
    Invoke-LoggedCommand -Root $Root -PhaseName 'release-install-drive' `
        -WorkingDirectory ([Environment]::GetFolderPath('System')) `
        -Executable "$env:WINDIR\System32\subst.exe" -Arguments @($Drive, '/D') `
        -EnvironmentValues @{} -TimeoutSeconds 60 | Out-Null
    $script:LastFailedInstallPhase = $failedInstallPhase
}

function Remove-DirectoryTree {
    param([Parameter(Mandatory=$true)][string]$Path)
    $nativePath = Resolve-NativePath $Path
    for ($attempt = 0; $attempt -lt 3 -and (Test-Path -LiteralPath $nativePath -PathType Container); $attempt++) {
        if ($attempt -gt 0) { Start-Sleep -Seconds 1 }
        Remove-Item -LiteralPath $nativePath -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $nativePath -PathType Container) {
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
from core.bootstrap.backend_bytecode import compile_backend_bytecode
from core.bootstrap.runtime_artifacts import ensure_runtime_artifacts_if_needed
from core.errors.exceptions import SoAIError

ensure_runtime_artifacts_if_needed(
    repo_root,
    python_executable=sys.executable,
)
print("Preparing SoAI backend bytecode...", flush=True)
try:
    compile_backend_bytecode(
        repo_root,
        progress=lambda entries: print(f"Prepared backend bytecode: {entries}", flush=True),
    )
except (SoAIError, OSError) as exception:
    print(f"Backend bytecode preparation failed; SoAI compiles on demand: {exception}", flush=True)
else:
    print("SoAI backend bytecode is ready.", flush=True)
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
        $realTiktokenDir = Join-Path $realStateDir 'tiktoken-cache'
        $realBackendDir = Resolve-ChildPath -Root $Root -Child 'backend'
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

        $artifactStartupAllowanceSeconds = ([SoAILauncher.NativeImageBudget]::Calculate(0, [string[]]@((Resolve-ChildPath -Root $Root -Child 'python'), $realVenvPath), [string[]]@(), [string[]]@(), 0)).WholeSeconds
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
                    -ProgressPaths @($realPlaywrightDir, $realJavaDir, $realTikaDir, $realTiktokenDir, $realBackendDir) `
                    -NoProgressTimeoutSeconds 300 `
                    -StartupAllowanceSeconds $artifactStartupAllowanceSeconds `
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

        if (![string]::IsNullOrWhiteSpace($env:SOAI_INSTALL_RETAINED_ROOT)) {
            Invoke-LoggedCommand `
                -Root $Root `
                -PhaseName 'preserve-plugin-selections' `
                -WorkingDirectory $realRepoRoot `
                -Executable $realVenvPython `
                -Arguments @('-P', '-m', 'app.updater.installation_plugin_upgrade', 'prepare', '--base-path', $realRepoRoot, '--source', $realRepoRoot, '--staged', $realRepoRoot, '--edition', 'soai-core', '--retained-installation-root', $env:SOAI_INSTALL_RETAINED_ROOT) `
                -EnvironmentValues $realEnvValues `
                -TimeoutSeconds 1200 | Out-Null
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
        Invoke-LoggedCommand `
            -Root $Root `
            -PhaseName 'protect-installation-activation' `
            -WorkingDirectory $realRepoRoot `
            -Executable $realVenvPython `
            -Arguments @('-P', '-m', 'app.updater.installation_plugin_upgrade', 'finish', '--base-path', $realRepoRoot, '--edition', 'soai-core') `
            -EnvironmentValues $realEnvValues `
            -TimeoutSeconds 1200 | Out-Null
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
                if ($attempt -eq 2 -or $script:LastFailedInstallPhase -in @('install-runtime-artifacts', 'preserve-plugin-selections', 'post-update-hook', 'protect-installation-activation')) {
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
        -Arguments @('--version') -EnvironmentValues @{} `
        -TimeoutSeconds (Get-PythonProbeTimeoutSeconds -Root $Root -PythonExe $pythonExe -OrdinarySeconds 60)
    $managedVersionLog = Invoke-LoggedCommand -Root $Root -PhaseName 'managed-python-version' `
        -WorkingDirectory ([Environment]::GetFolderPath('System')) -Executable $venvPython `
        -Arguments @('--version') -EnvironmentValues @{} `
        -TimeoutSeconds (Get-PythonProbeTimeoutSeconds -Root $Root -PythonExe $venvPython -OrdinarySeconds 60)
    foreach ($versionLog in @($runtimeVersionLog, $managedVersionLog)) {
        $installedVersion = ([string](Get-Content -LiteralPath $versionLog -Raw -Encoding UTF8)).Trim()
        if ($installedVersion -cne "Python $PythonVersion") {
            throw "Installed Python version mismatch: expected Python $PythonVersion; received $installedVersion. Diagnostic output: $versionLog"
        }
    }
    $state = @{
        product = 'SoAI'
        installed_at_utc = [DateTime]::UtcNow.ToString('o')
        python_runtime = (Get-Content -LiteralPath $runtimeVersionLog -Raw -Encoding UTF8).Trim()
        managed_python = (Get-Content -LiteralPath $managedVersionLog -Raw -Encoding UTF8).Trim()
        webview2_runtime = Get-WebView2RuntimeVersion
    } | ConvertTo-Json -Depth 3
    Set-Content -LiteralPath (Join-Path $stateDir 'windows-install.json') -Value $state -Encoding UTF8
}

function Invoke-RuntimeSecurityOperation {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][scriptblock]$Operation
    )
    try {
        & $Operation
    }
    catch {
        $failure = $_.Exception
        while ($null -ne $failure.InnerException) { $failure = $failure.InnerException }
        $description = $failure.Message
        if ($failure -is [ComponentModel.Win32Exception]) {
            $nativeFailure = [ComponentModel.Win32Exception]::new($failure.NativeErrorCode)
            $description = "Windows error $($failure.NativeErrorCode): $($nativeFailure.Message) $description"
        }
        throw [InvalidOperationException]::new("SoAI could not secure $Path. $description", $failure)
    }
}

function Set-RuntimePathSecurity {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Security
    )
    Invoke-RuntimeSecurityOperation -Path $Path -Operation { [SoAILauncher.InstallationSecurity]::Protect($Path, $Security) }
}

function Reset-RuntimePathSecurity {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$ParentSecurity
    )
    Invoke-RuntimeSecurityOperation -Path $Path -Operation { [SoAILauncher.InstallationSecurity]::ResetTree($Root, $Path, $ParentSecurity) }
}

function Set-RuntimeAccessControl {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [switch]$DeferUnsecuredInstallation
    )
    $rootPath = Resolve-FullPath $Root
    if ([IO.Directory]::GetDirectories((Resolve-NativePath $rootPath), '.soai_update_transaction_*').Count -gt 0) {
        Write-Step 'SoAI will secure its files the next time it starts after this update.'
        return
    }
    if ($DeferUnsecuredInstallation -and ![SoAILauncher.InstallationSecurity]::IsSecured($rootPath)) {
        Write-Step 'SoAI will secure its files the next time it starts.'
        return
    }
    $dataPath = Resolve-ChildPath -Root $rootPath -Child 'data'
    [void][IO.Directory]::CreateDirectory((Resolve-NativePath $dataPath))
    Write-Step "Securing SoAI files in $rootPath..."
    Set-RuntimePathSecurity -Path $rootPath -Security ([SoAILauncher.InstallationSecurity]::RootSecurity)
    foreach ($entry in [IO.Directory]::GetFileSystemEntries((Resolve-NativePath $rootPath))) {
        $name = [IO.Path]::GetFileName($entry)
        if (![string]::Equals($name, 'data', [StringComparison]::OrdinalIgnoreCase) `
            -and !$name.StartsWith('.soai_update_cleanup_', [StringComparison]::OrdinalIgnoreCase)) {
            Reset-RuntimePathSecurity -Root $rootPath -Path (Join-Path $rootPath $name) -ParentSecurity ([SoAILauncher.InstallationSecurity]::RootSecurity)
        }
    }
    Set-RuntimePathSecurity -Path $dataPath -Security ([SoAILauncher.InstallationSecurity]::DataSecurity)
    foreach ($entry in [IO.Directory]::GetFileSystemEntries((Resolve-NativePath $dataPath))) {
        Reset-RuntimePathSecurity -Root $rootPath -Path (Join-Path $dataPath ([IO.Path]::GetFileName($entry))) -ParentSecurity ([SoAILauncher.InstallationSecurity]::DataSecurity)
    }
    [SoAILauncher.InstallationSecurity]::CompleteSecuring($rootPath)
    Write-Step 'SoAI files are secured.'
}

function Test-SQLiteRuntimeAccess {
    param([Parameter(Mandatory=$true)][string]$Root)
    foreach ($relativePython in @('python\python.exe', 'soai_main_venv\Scripts\python.exe')) {
        $pythonExe = Resolve-ChildPath -Root $Root -Child $relativePython
        $phase = if ($relativePython -eq 'python\python.exe') { 'runtime-sqlite-import' } else { 'managed-sqlite-import' }
        Invoke-LoggedCommand -Root $Root -PhaseName $phase `
            -WorkingDirectory ([Environment]::GetFolderPath('System')) -Executable $pythonExe `
            -Arguments @('-c', 'import sqlite3; print(sqlite3.sqlite_version)') `
            -EnvironmentValues @{} -TimeoutSeconds (Get-PythonProbeTimeoutSeconds -Root $Root -PythonExe $pythonExe -OrdinarySeconds 60) | Out-Null
    }
}

if ($SecureAccessOnly) {
    if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
        throw 'InstallRoot is required to secure SoAI files.'
    }
    $resolvedInstallRoot = Resolve-FullPath $InstallRoot
    [Reflection.Assembly]::Load([IO.File]::ReadAllBytes((Resolve-NativePath (Resolve-ChildPath -Root $resolvedInstallRoot -Child 'soai.exe')))) | Out-Null
    Set-RuntimeAccessControl -Root $resolvedInstallRoot
    if ($CompleteInstallation) {
        $installationMarker = Join-Path $resolvedInstallRoot '.soai-install-root'
        if (![IO.File]::Exists((Resolve-NativePath $installationMarker))) {
            [SoAILauncher.NativeFilesystemHandles]::WriteNewDurableFile($installationMarker, 'SoAI Windows Installer Root')
        }
        Register-SoAISharedResourceClaim -InstallRoot $resolvedInstallRoot
    }
    exit 0
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
        -or @(Compare-Object $pythonDependencyFields @('package_sha256', 'url', 'version')).Count -ne 0) {
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
    if ($VisualCppRuntimeOnly) {
        Set-InstallProgress -Progress 43 -Message 'Preparing Microsoft Visual C++ runtime support...'
        Install-VisualCppRuntime -Root $resolvedInstallRoot
    }
    else {
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
            Set-InstallProgress -Progress 97 -Message 'Securing SoAI files...'
            Set-RuntimeAccessControl -Root $resolvedInstallRoot -DeferUnsecuredInstallation:$ExistingInstallation
            Test-SQLiteRuntimeAccess -Root $resolvedInstallRoot
            Register-SoAISharedResourceClaim -InstallRoot $resolvedInstallRoot
            Set-InstallProgress -Progress 98 -Message 'SoAI is ready to start.'
        }
    }
}
finally {
    Remove-DirectoryTree -Path $script:InstallerDownloadRoot
    Remove-DirectoryTree -Path $script:ReleasedInstallerDownloadRoot
}
exit 0
