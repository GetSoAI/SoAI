# SoAI - Windows payload filtering policy
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

$script:ExcludedAnyDirectoryNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(
    '.git',
    '.github',
    '.hg',
    '.svn',
    '.cache',
    '.coverage',
    '.idea',
    '.vscode',
    '.mypy_cache',
    '.nox',
    '.nyc_output',
    '.pytest_cache',
    '.ruff_cache',
    '.tmp',
    '.tox',
    '.vite',
    '__pycache__',
    '__snapshots__',
    'fixtures',
    'mockplugins',
    'mocks',
    'test',
    'tests',
    'unit',
    'coverage',
    'dist',
    'htmlcov',
    'node_modules',
    'out',
    'output',
    'playwright-output',
    'playwright-report',
    'screenshots',
    'test-logs',
    'test-results',
    'test-work',
    'tmp',
    '.soai-release-signing-gnupg',
    'openpgp-revocs.d',
    'private-keys-v1.d'
) | ForEach-Object { [void]$script:ExcludedAnyDirectoryNames.Add($_) }

$script:ExcludedRootDirectoryNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(
    '.windows-build',
    'python',
    'python-3.13',
    'runtime',
    'releases',
    'soai_main_venv',
    'soai_python',
    'webview2',
    'windows_release'
) | ForEach-Object { [void]$script:ExcludedRootDirectoryNames.Add($_) }

$script:ExcludedRelativeDirectories = @(
    'backend\core\bootstrap\launcher_posix',
    'data\backups',
    'data\backends',
    'data\cache',
    'data\chroma_rag',
    'data\database',
    'data\files',
    'data\gpu',
    'data\locks',
    'data\logs',
    'data\state',
    'data\temp',
    'data\user_files'
)

$script:ExcludedRootFiles = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(
    'create-soai-windows-installer.cmd',
    'create-soai-windows-installer.ps1',
    '.soai-windows-release.lock',
    'soai.exe',
    'soai.sh',
    'soai.command',
    'install-soai-from-release.sh',
    'install-soai-from-release.command',
    'microsoft.web.webview2.core.dll',
    'microsoft.web.webview2.winforms.dll',
    'webview2loader.dll',
    'data\secret.key'
) | ForEach-Object { [void]$script:ExcludedRootFiles.Add($_) }

$script:ExcludedFilePatterns = @(
    '.gitignore',
    '.bandit',
    '.depcheckrc',
    '.editorconfig',
    '.prettier*',
    'prettier.config.*',
    '.pylintrc',
    '.coveragerc',
    '.eslintrc*',
    '.stylelintrc*',
    'eslint.config.*',
    'stylelint.config.*',
    'conftest.py',
    'mypy.ini',
    'pyrightconfig.json',
    'pytest.ini',
    'requirements-dev.txt',
    'ruff.toml',
    '.ruff.toml',
    'tox.ini',
    'playwright.config.*',
    'playwright-test.d.ts',
    'vitest.config.*',
    'tsconfig.playwright.json',
    'test_*',
    'test-*',
    '*.test.*',
    '*.spec.*',
    '.coverage',
    '.coverage.*',
    '.ds_store',
    '.env',
    '.env.*',
    '.eslintcache',
    'coverage-final.json',
    'coverage.xml',
    'desktop.ini',
    'lcov.info',
    'thumbs.db',
    '*.cer',
    '*.crt',
    '*.dmp',
    '*.dump',
    '*.exe',
    '*.gpg',
    '*.har',
    '*.jks',
    '*.kbx',
    '*.key',
    '*.keystore',
    '*.map',
    '*.nupkg',
    '*.orig',
    '*.p12',
    '*.pcap',
    '*.pem',
    '*.pfx',
    '*.prof',
    '*.pyc',
    '*.pyo',
    '*.rej',
    '*.sqlite',
    '*.sqlite3',
    '*.status',
    '*.swo',
    '*.swp',
    '*.temp',
    '*.trace',
    '*.zip',
    '*.log',
    '*.tmp',
    '*.bak',
    '*.db',
    '*.soaiplugin.yaml',
    '*.soaiplugin.yml',
    'soai.exe.backup-*'
)

function Get-RelativePath {
    param(
        [Parameter(Mandatory=$true)][string]$Root,
        [Parameter(Mandatory=$true)][string]$Path
    )
    $prefix = $Root.TrimEnd('\') + '\'
    if (!$Path.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        return ''
    }
    return $Path.Substring($prefix.Length)
}

function Test-ExcludedDirectory {
    param([string]$RelativePath)
    if ([string]::IsNullOrWhiteSpace($RelativePath)) {
        return $false
    }
    $normalized = $RelativePath.Trim('\').ToLowerInvariant()
    $parts = $normalized -split '\\'
    foreach ($part in $parts) {
        if ($script:ExcludedAnyDirectoryNames.Contains($part) -or $part -like '*_check') {
            return $true
        }
    }
    if ($parts.Count -eq 1 -and $script:ExcludedRootDirectoryNames.Contains($normalized)) {
        return $true
    }
    foreach ($excluded in $script:ExcludedRelativeDirectories) {
        if ($normalized -eq $excluded -or $normalized.StartsWith($excluded + '\')) {
            return $true
        }
    }
    return $false
}

function Test-ExcludedFile {
    param(
        [string]$RelativePath,
        [string]$Name
    )
    $normalized = $RelativePath.Trim('\').ToLowerInvariant()
    if ($script:ExcludedRootFiles.Contains($normalized)) {
        return $true
    }
    foreach ($pattern in $script:ExcludedFilePatterns) {
        if ($Name -like $pattern) {
            return $true
        }
    }
    return $false
}

function Copy-FilteredTree {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination,
        [Parameter(Mandatory=$true)][string]$SourceRoot
    )
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $Source -Force) {
        $relative = Get-RelativePath -Root $SourceRoot -Path $item.FullName
        if ($item.PSIsContainer) {
            if (Test-ExcludedDirectory $relative) {
                continue
            }
            Copy-FilteredTree -Source $item.FullName -Destination (Join-Path $Destination $item.Name) -SourceRoot $SourceRoot
            continue
        }
        if (Test-ExcludedDirectory ([System.IO.Path]::GetDirectoryName($relative))) {
            continue
        }
        if (Test-ExcludedFile -RelativePath $relative -Name $item.Name) {
            continue
        }
        Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $Destination $item.Name) -Force
    }
}

function Assert-FilteredPayload {
    param(
        [Parameter(Mandatory=$true)][string]$PayloadRoot,
        [Parameter(Mandatory=$true)][System.Collections.Generic.HashSet[string]]$BuiltPayloadFiles,
        [switch]$PermitBuiltPayloadFiles
    )
    foreach ($item in Get-ChildItem -LiteralPath $PayloadRoot -Recurse -Force) {
        $relative = Get-RelativePath -Root $PayloadRoot -Path $item.FullName
        if ($item.PSIsContainer) {
            if (Test-ExcludedDirectory $relative) {
                throw "Windows payload contains a forbidden directory: $relative"
            }
            continue
        }
        $excludedFile = Test-ExcludedFile -RelativePath $relative -Name $item.Name
        $builtPayloadFile = $PermitBuiltPayloadFiles -and $BuiltPayloadFiles.Contains($relative)
        if ((Test-ExcludedDirectory ([System.IO.Path]::GetDirectoryName($relative))) `
            -or ($excludedFile -and !$builtPayloadFile)) {
            throw "Windows payload contains a generated or sensitive file: $relative"
        }
    }
}

Export-ModuleMember -Function Get-RelativePath, Copy-FilteredTree, Assert-FilteredPayload
