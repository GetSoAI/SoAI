Unicode true
XPStyle on
ManifestSupportedOS all
RequestExecutionLevel admin
SetCompressor /SOLID lzma
SetCompressorDictSize 64

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "nsDialogs.nsh"
!include "WinVer.nsh"
!include "x64.nsh"
!include "WinMessages.nsh"
!include "FileFunc.nsh"

!define SOAI_NATIVE_POWERSHELL "$WINDIR\Sysnative\WindowsPowerShell\v1.0\powershell.exe"

!ifndef PBM_SETPOS
  !define PBM_SETPOS 0x0402
!endif
!ifndef PBM_SETRANGE32
  !define PBM_SETRANGE32 0x0406
!endif

!ifndef PRODUCT_VERSION
  !error "PRODUCT_VERSION must be defined"
!endif
!ifndef PRODUCT_VERSION_QUAD
  !error "PRODUCT_VERSION_QUAD must be defined"
!endif
!ifndef PAYLOAD_DIR
  !error "PAYLOAD_DIR must be defined"
!endif
!ifndef OUTPUT_FILE
  !define OUTPUT_FILE "SoAI-Windows-x64-Setup.exe"
!endif
!ifndef ESTIMATED_SIZE_KB
  !define ESTIMATED_SIZE_KB "0"
!endif
!ifndef RUNTIME_FOOTPRINT_RESERVE_KB
  !define RUNTIME_FOOTPRINT_RESERVE_KB "0"
!endif
!ifndef PYTHON_VERSION
  !define PYTHON_VERSION "3.13.14"
!endif
!ifndef PYTHON_URL
  !define PYTHON_URL "https://www.nuget.org/api/v2/package/python/3.13.14"
!endif
!ifndef PYTHON_SHA256
  !define PYTHON_SHA256 "9AC15CFA6CAB1115C83D48F2AF55C554EFA4D1BB044BBC4AB1C9D17AD426E16C"
!endif
!ifndef WEBVIEW2_BOOTSTRAPPER_URL
  !define WEBVIEW2_BOOTSTRAPPER_URL "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
!endif
!ifndef LICENSE_FILE
  !define LICENSE_FILE "${PAYLOAD_DIR}\LICENSE.md"
!endif

!define PRODUCT_NAME "SoAI"
!define PRODUCT_PUBLISHER "SoAI"
!define PRODUCT_REGKEY "Software\SoAI"
!define PRODUCT_UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\SoAI"

Name "${PRODUCT_NAME}"
OutFile "${OUTPUT_FILE}"
InstallDir "$PROGRAMFILES64\SoAI"
InstallDirRegKey HKLM "${PRODUCT_REGKEY}" "InstallDir"

VIProductVersion "${PRODUCT_VERSION_QUAD}"
VIAddVersionKey /LANG=1033 "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey /LANG=1033 "CompanyName" "${PRODUCT_PUBLISHER}"
VIAddVersionKey /LANG=1033 "FileDescription" "SoAI Windows Installer"
VIAddVersionKey /LANG=1033 "FileVersion" "${PRODUCT_VERSION}"
VIAddVersionKey /LANG=1033 "ProductVersion" "${PRODUCT_VERSION}"
VIAddVersionKey /LANG=1033 "Comments" "SoAI installer supports /PrepareUpdate extraction without installation."
VIAddVersionKey /LANG=1033 "LegalCopyright" "SoAI"

!define MUI_ABORTWARNING
!define MUI_CUSTOMFUNCTION_ABORT AbortSoAIInstall
!define MUI_ICON "assets\soai-installer.ico"
!define MUI_UNICON "assets\soai-installer.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "assets\header.bmp"
!define MUI_WELCOMEFINISHPAGE_BITMAP "assets\welcome.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "assets\welcome.bmp"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Start SoAI"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchSoAIFromFinish
!define MUI_WELCOMEPAGE_TEXT "Setup will guide you through the installation of SoAI.$\r$\n$\r$\nAn internet connection is required to install SoAI.$\r$\n$\r$\nClose other applications before continuing, then click Next."

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${LICENSE_FILE}"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
Page custom RuntimePrepPageCreate RuntimePrepPageLeave
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Var RuntimeStatusPath
Var RuntimeExitPath
Var RuntimeErrorPath
Var RuntimeWrapperPath
Var LastRuntimeStatusMessage
Var RuntimePollTicks
Var RuntimeNoStatusTicks
Var RuntimeCurrentProgress
Var RuntimePageDialog
Var RuntimePageStatusLabel
Var RuntimePageProgress
Var RuntimePageDetailLabel
Var RuntimePrepFailed
Var RuntimePrepFinished
Var UpgradeBackupRoot
Var UpgradePrepared
Var UpgradeRollbackCompleted
Var InstallerMutexHandle
Var InstallMutationStarted
Var UpdateStageRoot

!include "includes\InstallLifecycle.nsh"
!include "includes\RuntimePreparation.nsh"
!include "includes\WindowsIntegration.nsh"

Section "SoAI" SEC_SOAI
  SetShellVarContext all
  SetRegView 64
  AddSize ${RUNTIME_FOOTPRINT_RESERVE_KB}

  ${If} $UpdateStageRoot == ""
    Call PrepareInstallerTransactionTools
    Call StopExistingSoAI
    Call PrepareExistingInstallRoot

    StrCpy $InstallMutationStarted 1
    CreateDirectory "$INSTDIR"
    FileOpen $0 "$INSTDIR\.soai-install-root" w
    FileWrite $0 "SoAI Windows Installer Root$\r$\n"
    FileWrite $0 "Version=${PRODUCT_VERSION}$\r$\n"
    FileClose $0
  ${Else}
    Call ValidateUpdateStageRoot
    StrCpy $INSTDIR "$UpdateStageRoot"
  ${EndIf}
  SetOutPath "$INSTDIR"
  ClearErrors
  !include "${PAYLOAD_FILES_INCLUDE}"
  ${If} ${Errors}
    SetErrorLevel 1
    Abort
  ${EndIf}
  Call InstallCandidateLauncher
  ${If} $UpdateStageRoot != ""
    Goto done
  ${EndIf}
  Push 35
  Call SetInstallerProgress

  IfSilent 0 done
    Call RuntimePrepRunSilent
  done:

SectionEnd

Section "Uninstall"
  SetShellVarContext all
  SetRegView 64

  IfFileExists "$INSTDIR\installer-support\Remove-SoAI.ps1" 0 cleanup_registry
    DetailPrint "Removing SoAI runtime, app files, and data..."
    SetOutPath "$TEMP"
    nsExec::ExecToLog '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "$INSTDIR\installer-support\Remove-SoAI.ps1" -InstallRoot "$INSTDIR" -Mode Uninstall'
    Pop $0
    ${If} $0 != 0
      ${IfNot} ${Silent}
        MessageBox MB_ICONSTOP|MB_OK "SoAI cleanup did not complete. Close any running setup or launcher. If an update awaits recovery, reopen SoAI to complete it before retrying uninstall."
      ${EndIf}
      SetErrorLevel 1
      Abort
    ${EndIf}

  cleanup_registry:
  Call un.RemoveSoAITypeFonts
  Delete "$SMPROGRAMS\SoAI\SoAI.lnk"
  Delete "$SMPROGRAMS\SoAI\Uninstall SoAI.lnk"
  RMDir "$SMPROGRAMS\SoAI"
  Delete "$DESKTOP\SoAI.lnk"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKLM "${PRODUCT_REGKEY}"
  DeleteRegKey HKLM "${PRODUCT_UNINSTALL_KEY}"
SectionEnd
