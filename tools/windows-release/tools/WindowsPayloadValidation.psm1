# SoAI - Windows payload content validation
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

function Assert-WindowsLicenseInventory {
    param([Parameter(Mandatory=$true)][string]$PayloadRoot)
    $licensesRoot = Join-Path $PayloadRoot 'licenses'
    if (!(Test-Path -LiteralPath $licensesRoot -PathType Container)) {
        throw 'Windows payload lacks its licenses directory.'
    }
    $expected = @(
        'Apache-2.0.txt',
        'Azul-Zulu-NOTICE.txt',
        'CDDL-1.0.txt',
        'FRONTEND-THIRD-PARTY-LICENSES.txt',
        'MIT.txt',
        'MSVC-RUNTIME-NOTICE.txt',
        'NSIS-LICENSE.txt',
        'OFL.txt',
        'OPTIONAL-NATIVE-DEPENDENCY-NOTICES.txt',
        'OpenJDK-ADDITIONAL-LICENSE-INFO.txt',
        'OpenJDK-GPLv2.txt',
        'OpenSSL-NOTICE.txt',
        'PLAYWRIGHT-CHROMIUM-NOTICES.txt',
        'PYTHON-THIRD-PARTY-NOTICES.txt',
        'Python-3.13-LICENSE.txt',
        'SBOM-OPTIONAL-NATIVE-CYCLONEDX.json',
        'SBOM-PYTHON-CYCLONEDX.json',
        'TESSERACT-WINDOWS-RUNTIME-NOTICES.txt',
        'THIRD_PARTY_BACKEND_LICENSES.md',
        'THIRD_PARTY_LOGO_NOTICES.md',
        'TIKA-RUNTIME-NOTICES.txt',
        'WINDOWS-THIRD-PARTY-NOTICES.txt',
        'legal_document_catalog.json',
        'libffi-NOTICE.txt',
        'webview2'
    ) | Sort-Object
    $licenseEntries = @(Get-ChildItem -LiteralPath $licensesRoot -Force)
    $actual = @($licenseEntries | Select-Object -ExpandProperty Name | Sort-Object)
    if ((Compare-Object -ReferenceObject $expected -DifferenceObject $actual).Count -ne 0) {
        throw 'Windows payload license inventory does not match the platform contract.'
    }
    $invalidLicenseEntries = @(
        $licenseEntries | Where-Object {
            ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -or
            ($_.Name -eq 'webview2' -and !$_.PSIsContainer) -or
            ($_.Name -ne 'webview2' -and $_.PSIsContainer)
        }
    )
    if ($invalidLicenseEntries.Count -ne 0) {
        throw 'Windows payload license material has an invalid file type.'
    }
    $webViewLicensesRoot = Join-Path $licensesRoot 'webview2'
    if (!(Test-Path -LiteralPath $webViewLicensesRoot -PathType Container)) {
        throw 'Windows payload WebView2 license directory is invalid.'
    }
    $expectedWebViewLicenses = @(
        'Microsoft.Web.WebView2.SDK-LICENSE.txt',
        'Microsoft.Web.WebView2.SDK-NOTICE.txt',
        'README.txt'
    ) | Sort-Object
    $webViewLicenseEntries = @(Get-ChildItem -LiteralPath $webViewLicensesRoot -Force)
    $actualWebViewLicenses = @($webViewLicenseEntries | Select-Object -ExpandProperty Name | Sort-Object)
    if ((Compare-Object -ReferenceObject $expectedWebViewLicenses -DifferenceObject $actualWebViewLicenses).Count -ne 0 `
        -or @($webViewLicenseEntries | Where-Object {
            $_.PSIsContainer -or ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint)
        }).Count -ne 0) {
        throw 'Windows payload WebView2 license inventory does not match the platform contract.'
    }
}

function Assert-WindowsPlatformPayload {
    param([Parameter(Mandatory=$true)][string]$PayloadRoot)
    $posixLauncher = Join-Path $PayloadRoot 'backend\core\bootstrap\launcher_posix'
    if (Test-Path -LiteralPath $posixLauncher) {
        throw 'Windows payload contains POSIX launcher material.'
    }
    $foreignFiles = @(
        Get-ChildItem -LiteralPath $PayloadRoot -Recurse -File -Force |
            Where-Object { $_.Extension -in @('.sh', '.command') }
    )
    if ($foreignFiles.Count -ne 0) {
        throw 'Windows payload contains foreign-platform executable material.'
    }
}

Export-ModuleMember -Function Assert-WindowsLicenseInventory, Assert-WindowsPlatformPayload
