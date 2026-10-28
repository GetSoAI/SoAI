# SoAI Windows shared backend ownership contract [Shared-SoAIResourceOwnership.ps1]
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

Set-StrictMode -Version 3.0

function Invoke-WithSoAISharedResourceRegistry {
    param(
        [Parameter(Mandatory=$true)][scriptblock]$Operation
    )
    $programData = [Environment]::GetFolderPath([Environment+SpecialFolder]::CommonApplicationData)
    if ([string]::IsNullOrWhiteSpace($programData)) { throw 'Windows shared application data is unavailable.' }
    $ownershipRoot = [IO.Path]::Combine($programData, 'SoAI')
    $gate = [SoAILauncher.NativeFilesystemHandles]::AcquireSharedResourceGate()
    $lock = $null
    $completed = $false
    $removeRoot = $false
    try {
        [IO.Directory]::CreateDirectory($ownershipRoot) | Out-Null
        $ownershipAttributes = [IO.File]::GetAttributes($ownershipRoot)
        if (($ownershipAttributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'The SoAI shared-resource ownership root is a reparse point.'
        }
        $lockPath = [IO.Path]::Combine($ownershipRoot, 'shared-resource-ownership-v1.lock')
        Assert-SoAISharedOwnershipEntry -Path $lockPath
        $lock = [SoAILauncher.NativeFilesystemHandles]::CreateFile($lockPath, 0x10083, 0, [IntPtr]::Zero, 4, 0x00200000, [IntPtr]::Zero)
        if ($lock.IsInvalid) { throw 'Shared backend ownership is busy or inaccessible. No shared resources were changed.' }
        Repair-SoAISharedResourceRegistry -OwnershipRoot $ownershipRoot
        & $Operation $ownershipRoot
        $completed = $true
        $removeRoot = Remove-SoAIEmptyOwnershipArtifacts -OwnershipRoot $ownershipRoot -OwnershipLock $lock
    }
    finally {
        if ($null -ne $lock) { $lock.Dispose() }
        try { if ($completed -and $removeRoot) { [IO.Directory]::Delete($ownershipRoot, $false) } }
        finally { $gate.ReleaseMutex(); $gate.Dispose() }
    }
}

function Assert-SoAISharedOwnershipEntry {
    param([Parameter(Mandatory=$true)][string]$Path)
    try { $attributes = [IO.File]::GetAttributes($Path) }
    catch [IO.FileNotFoundException] { return }
    catch [IO.DirectoryNotFoundException] { return }
    if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Shared backend ownership evidence is a reparse point and was retained for repair.'
    }
}

function Remove-SoAIEmptyOwnershipArtifacts {
    param(
        [Parameter(Mandatory=$true)][string]$OwnershipRoot,
        [Parameter(Mandatory=$true)][Microsoft.Win32.SafeHandles.SafeFileHandle]$OwnershipLock
    )
    if (![IO.Directory]::Exists($OwnershipRoot)) { return }
    $registry = Read-SoAISharedResourceRegistry -OwnershipRoot $OwnershipRoot
    if ($null -ne $registry -and @($registry.installations).Count -ne 0) { return }
    $allowed = @('shared-resource-claims-v1.json', 'shared-resource-ownership-v1.lock')
    foreach ($entry in [IO.Directory]::GetFileSystemEntries($OwnershipRoot)) {
        if ([IO.Path]::GetFileName($entry) -notin $allowed) { return }
        Assert-SoAISharedOwnershipEntry -Path $entry
    }
    [SoAILauncher.NativeFilesystemHandles]::RemoveEmptySharedOwnership($OwnershipRoot, $OwnershipLock)
    return $true
}

function Read-SoAISharedResourceRegistry {
    param(
        [Parameter(Mandatory=$true)][string]$OwnershipRoot,
        [string]$RegistryPath = ''
    )
    $path = if ($RegistryPath) { [IO.Path]::GetFullPath($RegistryPath) } else { [IO.Path]::Combine($OwnershipRoot, 'shared-resource-claims-v1.json') }
    if ($RegistryPath -and (![string]::Equals([IO.Path]::GetDirectoryName($path), [IO.Path]::GetFullPath($OwnershipRoot).TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName($path) -cnotmatch '^shared-resource-claims-v1\.json\.previous-[0-9a-f]{32}$')) {
        throw 'Shared backend ownership recovery evidence is outside its operation boundary.'
    }
    Assert-SoAISharedOwnershipEntry -Path $path
    if (![IO.File]::Exists($path)) { return $null }
    $registry = [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8) | ConvertFrom-Json
    if ($null -eq $registry -or $registry.schema_version -ne 1 -or $registry.installations -isnot [array] `
        -or ($registry.schema_version -isnot [int] -and $registry.schema_version -isnot [long])) {
        throw 'Shared backend ownership evidence is malformed and was retained for repair.'
    }
    $claimIds = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($claim in @($registry.installations)) {
        if ($null -eq $claim -or $claim.claim_id -cnotmatch '^[0-9a-f]{64}$' `
            -or [string]::IsNullOrWhiteSpace($claim.install_root) `
            -or ![IO.Path]::IsPathRooted($claim.install_root) `
            -or $claim.retained_data -isnot [bool] `
            -or !$claimIds.Add([string]$claim.claim_id) `
            -or $claim.claim_id -cne (Get-SoAIInstallationClaimId -InstallRoot $claim.install_root)) {
            throw 'Shared backend ownership evidence is malformed and was retained for repair.'
        }
    }
    return $registry
}

function Repair-SoAISharedResourceRegistry {
    param([Parameter(Mandatory=$true)][string]$OwnershipRoot)
    $path = [IO.Path]::Combine($OwnershipRoot, 'shared-resource-claims-v1.json')
    Assert-SoAISharedOwnershipEntry -Path $path
    if ([IO.File]::Exists($path)) { return }
    $backups = @()
    $pending = $false
    foreach ($entry in [IO.Directory]::GetFileSystemEntries($OwnershipRoot)) {
        $name = [IO.Path]::GetFileName($entry)
        if ($name -cmatch '^shared-resource-claims-v1\.json\.previous-[0-9a-f]{32}$') { $backups += $entry }
        if ($name -cmatch '^shared-resource-claims-v1\.json\.next-[0-9a-f]{32}$') { $pending = $true }
    }
    if ($backups.Count -eq 0 -and !$pending) { return }
    if ($backups.Count -ne 1) {
        throw 'Shared ownership replacement was interrupted and its previous registry is ambiguous. Recovery evidence was retained for repair.'
    }
    $previous = Read-SoAISharedResourceRegistry -OwnershipRoot $OwnershipRoot -RegistryPath $backups[0]
    if ($null -eq $previous) { throw 'The previous shared ownership registry is unavailable. Recovery evidence was retained for repair.' }
    [IO.File]::Move($backups[0], $path)
}

function Assert-SoAISharedResourceRelease {
    param(
        [Parameter(Mandatory=$true)][string]$InstallRoot,
        [Parameter(Mandatory=$true)][bool]$RetainData
    )
    Invoke-WithSoAISharedResourceRegistry {
        param($ownershipRoot)
        $registry = Read-SoAISharedResourceRegistry -OwnershipRoot $ownershipRoot
        $claims = @(if ($null -ne $registry) { $registry.installations })
        $claimId = Get-SoAIInstallationClaimId -InstallRoot $InstallRoot
        $current = @($claims | Where-Object { $_.claim_id -ceq $claimId })
        if ($RetainData) {
            if ($current.Count -ne 1 -or !$current[0].retained_data) {
                throw 'The retained-data ownership claim was not verified. Uninstall registration was retained for repair.'
            }
        }
        elseif ($current.Count -ne 0) {
            throw 'Application-data cleanup retained its shared-resource ownership claim.'
        }
        if ($claims.Count -eq 0 -and (Test-SoAISharedBackendPresence -BackendRoot ([IO.Path]::Combine($ownershipRoot, 'backends')))) {
            throw 'Shared backend resources remain without verified ownership.'
        }
    }
}

function Write-SoAISharedResourceRegistry {
    param(
        [Parameter(Mandatory=$true)][string]$OwnershipRoot,
        [Parameter(Mandatory=$true)][AllowEmptyCollection()][object[]]$Installations
    )
    $path = [IO.Path]::Combine($OwnershipRoot, 'shared-resource-claims-v1.json')
    $temporary = $path + '.next-' + [Guid]::NewGuid().ToString('N')
    $backup = $path + '.previous-' + [Guid]::NewGuid().ToString('N')
    Assert-SoAISharedOwnershipEntry -Path $path
    $payload = [ordered]@{ schema_version = 1; installations = @($Installations) } | ConvertTo-Json -Depth 4
    $succeeded = $false
    $previous = if ([IO.File]::Exists($path)) { [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8) } else { $null }
    try {
        $stream = [IO.File]::Open($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try {
            $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($payload)
            $stream.Write($bytes, 0, $bytes.Length)
            $stream.Flush($true)
        } finally { $stream.Dispose() }
        if ([IO.File]::Exists($path)) {
            try { [IO.File]::Replace($temporary, $path, $backup, $false) }
            catch {
                if (![IO.File]::Exists($path) -and [IO.File]::Exists($backup)) {
                    Assert-SoAISharedOwnershipEntry -Path $backup
                    if ([IO.File]::ReadAllText($backup, [Text.Encoding]::UTF8) -cne $previous) {
                        throw 'Ownership replacement failed and its backup identity could not be verified. Recovery evidence was retained.'
                    }
                    [IO.File]::Move($backup, $path)
                }
                if (![IO.File]::Exists($path) -or [IO.File]::ReadAllText($path, [Text.Encoding]::UTF8) -cne $previous) {
                    throw 'Ownership replacement failed and the previous registry could not be verified. Recovery evidence was retained.'
                }
                throw
            }
        }
        else {
            [IO.File]::Move($temporary, $path)
        }
        if ([IO.File]::ReadAllText($path, [Text.Encoding]::UTF8) -cne $payload) {
            throw 'Shared backend ownership replacement could not be verified. Recovery evidence was retained.'
        }
        $succeeded = $true
    }
    finally {
        if ($succeeded) {
            if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
            if ([IO.File]::Exists($backup)) { [IO.File]::Delete($backup) }
        }
    }
}

function Get-SoAIInstallationClaimId {
    param([Parameter(Mandatory=$true)][string]$InstallRoot)
    $normalized = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\').ToUpperInvariant()
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($normalized))).Replace('-', '').ToLowerInvariant()) }
    finally { $sha.Dispose() }
}

function Register-SoAISharedResourceClaim {
    param([Parameter(Mandatory=$true)][string]$InstallRoot)
    $root = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
    Assert-SoAISharedOwnershipEntry -Path $root
    $marker = [IO.Path]::Combine($root, '.soai-install-root')
    if (![IO.File]::Exists($marker)) { throw 'Shared backend ownership requires a verified SoAI installation root.' }
    Assert-SoAISharedOwnershipEntry -Path $marker
    Invoke-WithSoAISharedResourceRegistry {
        param($ownershipRoot)
        $registry = Read-SoAISharedResourceRegistry -OwnershipRoot $ownershipRoot
        $claims = @(if ($null -ne $registry) { $registry.installations })
        $claimId = Get-SoAIInstallationClaimId -InstallRoot $root
        $remaining = @($claims | Where-Object { $_.claim_id -ne $claimId })
        $remaining += [ordered]@{ claim_id = $claimId; install_root = $root; retained_data = $false }
        Write-SoAISharedResourceRegistry -OwnershipRoot $ownershipRoot -Installations $remaining
    }
}

function Assert-SoAISharedBackendTree {
    param([Parameter(Mandatory=$true)][string]$BackendRoot)
    if (!(Test-SoAISharedBackendPresence -BackendRoot $BackendRoot)) { return }
    $root = Get-Item -LiteralPath $BackendRoot -Force -ErrorAction Stop
    if (($root.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The shared backend root is a reparse point; it was retained for repair.'
    }
    foreach ($entry in Get-ChildItem -LiteralPath $BackendRoot -Force -Recurse -ErrorAction Stop) {
        if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'A shared backend entry is a reparse point; shared resources were retained for repair.'
        }
    }
}

function Test-SoAISharedBackendPresence {
    param([Parameter(Mandatory=$true)][string]$BackendRoot)
    try { $attributes = [IO.File]::GetAttributes($BackendRoot) }
    catch [IO.FileNotFoundException] { return $false }
    catch [IO.DirectoryNotFoundException] { return $false }
    if (($attributes -band [IO.FileAttributes]::Directory) -eq 0) {
        throw 'Shared backend storage is not a verified directory. Ownership and resources were retained for repair.'
    }
    return $true
}

function Release-SoAISharedResourceClaim {
    param(
        [Parameter(Mandatory=$true)][string]$InstallRoot,
        [Parameter(Mandatory=$true)][bool]$RetainData,
        [string]$ReleaseJournalPath = ''
    )
    $root = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
    Assert-SoAISharedOwnershipEntry -Path $root
    Invoke-WithSoAISharedResourceRegistry {
        param($ownershipRoot)
        $backendRoot = [IO.Path]::Combine($ownershipRoot, 'backends')
        $backendPresent = Test-SoAISharedBackendPresence -BackendRoot $backendRoot
        $registry = Read-SoAISharedResourceRegistry -OwnershipRoot $ownershipRoot
        if ($null -eq $registry) {
            if ($backendPresent) {
                throw 'Shared plugin backends predate ownership tracking and were retained. Reinstall SoAI to establish ownership before retrying removal.'
            }
        }
        $claims = @(if ($null -ne $registry) { $registry.installations })
        $claimId = Get-SoAIInstallationClaimId -InstallRoot $root
        $current = @($claims | Where-Object { $_.claim_id -eq $claimId })
        $remaining = @($claims | Where-Object { $_.claim_id -ne $claimId })
        if (!$RetainData) {
            foreach ($claim in $remaining) {
                Assert-SoAISharedOwnershipEntry -Path $claim.install_root
                $otherMarker = [IO.Path]::Combine([string]$claim.install_root, '.soai-install-root')
                if (!$claim.retained_data -and ![IO.File]::Exists($otherMarker)) {
                    throw 'Another shared-backend claim cannot be verified. Shared resources and retry evidence were retained.'
                }
                Assert-SoAISharedOwnershipEntry -Path $otherMarker
            }
        }
        $releaseAdmitted = $false
        if ($ReleaseJournalPath) {
            Assert-SoAISharedOwnershipEntry -Path $ReleaseJournalPath
            if ([IO.File]::Exists($ReleaseJournalPath)) {
                if ($RetainData -or [IO.File]::ReadAllText($ReleaseJournalPath, [Text.Encoding]::UTF8) -cne ("all`n" + $root)) {
                    throw 'Shared ownership release recovery evidence conflicts with this removal. No shared resources were changed.'
                }
                $releaseAdmitted = $true
            }
        }
        if ($current.Count -ne 1 -or ![string]::Equals([IO.Path]::GetFullPath($current[0].install_root).TrimEnd('\'), $root, [StringComparison]::OrdinalIgnoreCase)) {
            if (!$RetainData -and $releaseAdmitted -and $current.Count -eq 0) { return }
            if ($backendPresent) {
                throw 'This installation has no exclusive shared-backend claim. Shared resources were retained.'
            }
            if ($RetainData) {
                $marker = [IO.Path]::Combine($root, '.soai-install-root')
                if (![IO.File]::Exists($marker)) { throw 'Retaining an untracked installation requires its verified installation marker.' }
                Assert-SoAISharedOwnershipEntry -Path $marker
                $claims += [ordered]@{ claim_id = $claimId; install_root = $root; retained_data = $true }
                Write-SoAISharedResourceRegistry -OwnershipRoot $ownershipRoot -Installations $claims
            }
            return
        }
        if ($RetainData) {
            $remaining += [ordered]@{ claim_id = $claimId; install_root = $root; retained_data = $true }
            Write-SoAISharedResourceRegistry -OwnershipRoot $ownershipRoot -Installations $remaining
            return
        }
        if ($remaining.Count -eq 0 -and $backendPresent) {
            Assert-SoAISharedBackendTree -BackendRoot $backendRoot
        }
        if ($ReleaseJournalPath -and !$releaseAdmitted) {
            [SoAILauncher.NativeFilesystemHandles]::WriteNewDurableFile($ReleaseJournalPath, ("all`n" + $root))
        }
        if ($remaining.Count -eq 0 -and $backendPresent) {
            Remove-Item -LiteralPath $backendRoot -Recurse -Force -ErrorAction Stop
            if (Test-SoAISharedBackendPresence -BackendRoot $backendRoot) { throw 'Shared plugin backend cleanup did not complete.' }
        }
        Write-SoAISharedResourceRegistry -OwnershipRoot $ownershipRoot -Installations $remaining
    }
}
