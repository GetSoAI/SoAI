; SoAI - Windows installer lifecycle [tools/windows-release/installer/includes/InstallLifecycle.nsh]
; SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP|MB_OK "SoAI for Windows requires 64-bit Windows."
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP|MB_OK "SoAI requires Windows 10 or later. Windows 11 is recommended."
    Abort
  ${EndIf}
  SetRegView 64
FunctionEnd
Function un.onInit
  SetShellVarContext all
  SetRegView 64
  ReadRegStr $0 HKLM "${PRODUCT_REGKEY}" "InstallDir"
  ${If} $0 != ""
    StrCpy $INSTDIR "$0"
  ${Else}
    StrCpy $INSTDIR "$EXEDIR"
  ${EndIf}
FunctionEnd
Function StopExistingSoAI
  IfFileExists "$INSTDIR\soai.exe" 0 done
    DetailPrint "Stopping any running SoAI instance..."
    nsExec::ExecToLog '"$INSTDIR\soai.exe" stop'
    Pop $0
  done:
FunctionEnd
Function PrepareExistingInstallRoot
  IfFileExists "$INSTDIR\.soai-install-root" has_existing
  IfFileExists "$INSTDIR\soai.exe" has_existing
  Goto done

  has_existing:
    SetOutPath "$INSTDIR\installer-support"
    File "${PAYLOAD_DIR}\installer-support\Remove-SoAI.ps1"

    ReadRegStr $1 HKLM "${PRODUCT_UNINSTALL_KEY}" "InstallLocation"
    SetOutPath "$TEMP"
    ${If} $1 == "$INSTDIR"
      DetailPrint "Cleaning files from the previous SoAI installation..."
      nsExec::ExecToLog '"$WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "$INSTDIR\installer-support\Remove-SoAI.ps1" -InstallRoot "$INSTDIR" -Mode Upgrade'
    ${Else}
      DetailPrint "Removing an incomplete previous SoAI installation..."
      nsExec::ExecToLog '"$WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "$INSTDIR\installer-support\Remove-SoAI.ps1" -InstallRoot "$INSTDIR" -Mode Uninstall'
    ${EndIf}
    Pop $0
    ${If} $0 != 0
      MessageBox MB_ICONSTOP|MB_OK "The previous SoAI installation could not be cleaned. Close SoAI, wait for any previous setup window to finish, and run this installer again."
      Abort
    ${EndIf}
  done:
FunctionEnd
Function LaunchSoAIFromFinish
  Exec '"$INSTDIR\soai.exe"'
FunctionEnd
