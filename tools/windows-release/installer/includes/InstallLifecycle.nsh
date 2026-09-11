; SoAI - Windows installer lifecycle [tools/windows-release/installer/includes/InstallLifecycle.nsh]
; SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

Function .onInit
  System::Call 'kernel32::CreateMutex(p 0, i 0, t "Global\SoAI.WindowsInstaller.V1") p .r1 ?e'
  Pop $0
  StrCpy $InstallerMutexHandle $1
  ${If} $InstallerMutexHandle == 0
    MessageBox MB_ICONSTOP|MB_OK "Setup could not acquire the SoAI installer lock. Close any other setup window and run this installer again."
    Abort
  ${EndIf}
  ${If} $0 == 183
    MessageBox MB_ICONSTOP|MB_OK "Another SoAI setup is already running. Finish or close it before starting this installer."
    Abort
  ${EndIf}
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP|MB_OK "SoAI for Windows requires 64-bit Windows."
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP|MB_OK "SoAI requires Windows 10 or later. Windows 11 is recommended."
    Abort
  ${EndIf}
  SetRegView 64
  StrCpy $UpgradeBackupRoot ""
  StrCpy $UpgradePrepared 0
  StrCpy $UpgradeRollbackCompleted 0
  StrCpy $InstallMutationStarted 0
  StrCpy $UpdateStageRoot ""
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/PrepareUpdate=" $UpdateStageRoot
  ${IfNot} ${Errors}
    ${If} $UpdateStageRoot == ""
    ${OrIfNot} ${Silent}
      SetErrorLevel 1
      Abort
    ${EndIf}
    Call ValidateUpdateStageRoot
  ${EndIf}
FunctionEnd
Function ValidateUpdateStageRoot
  ClearErrors
  GetFullPathName $UpdateStageRoot "$UpdateStageRoot"
  ${If} ${Errors}
    SetErrorLevel 1
    Abort
  ${EndIf}
  ${GetRoot} "$UpdateStageRoot" $0
  ${If} $UpdateStageRoot == "$0"
  ${OrIf} $UpdateStageRoot == "$0\"
    SetErrorLevel 1
    Abort
  ${EndIf}
  StrCpy $2 "$UpdateStageRoot"
  stage_parent:
    System::Call 'kernel32::GetFileAttributes(t r2) i .r0'
    ${If} $0 == -1
      SetErrorLevel 1
      Abort
    ${EndIf}
    IntOp $1 $0 & 0x410
    ${If} $1 <> 0x10
      SetErrorLevel 1
      Abort
    ${EndIf}
    ${GetParent} "$2" $1
    ${If} $1 != ""
    ${AndIf} $1 != "$2"
      StrCpy $2 "$1"
      Goto stage_parent
    ${EndIf}
  Push "$UpdateStageRoot"
  Call InspectInstallerDirectory
  Pop $0
  ${If} $0 != "empty"
    SetErrorLevel 1
    Abort
  ${EndIf}
FunctionEnd
Function InspectInstallerDirectory
  Exch $0
  Push $1
  Push $2
  Push $3
  Push $4
  System::Call 'kernel32::GetFileAttributes(t r0) i .r1'
  IntOp $1 $1 & 0x410
  ${If} $1 <> 0x10
    Goto unavailable
  ${EndIf}
  System::Call '*(i,l,l,l,i,i,i,i,&t260,&t14) p .r2'
  ${If} $2 == 0
    Goto unavailable
  ${EndIf}
  System::Call 'kernel32::FindFirstFile(t "$0\*", p r2) p .r0 ?e'
  Pop $4
  ${If} $0 == -1
    System::Free $2
    ${If} $4 == 2
      Goto empty
    ${EndIf}
    Goto unavailable
  ${EndIf}
  inspect_entry:
    System::Call '*$2(i,l,l,l,i,i,i,i,&t260 .r1,&t14)'
    ${If} $1 != "."
    ${AndIf} $1 != ".."
      System::Call 'kernel32::FindClose(p r0) i .r3'
      System::Free $2
      ${If} $3 == 0
        Goto unavailable
      ${EndIf}
      StrCpy $0 "nonempty"
      Goto done
    ${EndIf}
    System::Call 'kernel32::FindNextFile(p r0, p r2) i .r3 ?e'
    Pop $4
    ${If} $3 != 0
      Goto inspect_entry
    ${EndIf}
    System::Call 'kernel32::FindClose(p r0) i .r3'
    System::Free $2
    ${If} $3 != 0
    ${AndIf} $4 == 18
      Goto empty
    ${EndIf}
    Goto unavailable
  empty:
    StrCpy $0 "empty"
    Goto done
  unavailable:
    StrCpy $0 "unavailable"
  done:
    Pop $4
    Pop $3
    Pop $2
    Pop $1
    Exch $0
FunctionEnd
Function .onInstFailed
  ${If} $UpgradeRollbackCompleted == 1
    Return
  ${EndIf}
  ${If} $UpgradePrepared == 1
    Call RestoreExistingInstallRoot
  ${ElseIf} $InstallMutationStarted == 1
    Call CleanupFailedFreshInstall
  ${EndIf}
FunctionEnd
Function .onInstSuccess
  Call CleanupUpgradeBackup
FunctionEnd
Function AbortSoAIInstall
  ${If} $UpgradeRollbackCompleted == 1
    Return
  ${EndIf}
  ${If} $UpgradePrepared == 1
    Call RestoreExistingInstallRoot
  ${ElseIf} $InstallMutationStarted == 1
    Call CleanupFailedFreshInstall
  ${EndIf}
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
    nsExec::ExecToLog '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "$PLUGINSDIR\Remove-SoAI.ps1" -InstallRoot "$INSTDIR" -Mode Stop'
    Pop $0
    ${If} $0 != 0
      SetErrorLevel 1
      ${IfNot} ${Silent}
        MessageBox MB_ICONSTOP|MB_OK "SoAI could not be stopped safely. Close SoAI and retry setup. No application files were replaced."
      ${EndIf}
      Abort
    ${EndIf}
  done:
FunctionEnd
Function PrepareInstallerTransactionTools
  InitPluginsDir
  SetOutPath "$PLUGINSDIR"
  File /oname=Remove-SoAI.ps1 "${PAYLOAD_DIR}\installer-support\Remove-SoAI.ps1"
  File /oname=Preserve-SoAIUpgrade.ps1 "${PAYLOAD_DIR}\installer-support\Preserve-SoAIUpgrade.ps1"
  File /oname=installed-files.txt "${PAYLOAD_DIR}\installer-support\installed-files.txt"
FunctionEnd
Function InstallCandidateLauncher
  ClearErrors
  ${If} $UpdateStageRoot != ""
    SetOutPath "$INSTDIR"
    File /oname=soai.exe "${PAYLOAD_DIR}\soai.exe"
    ${If} ${Errors}
      SetErrorLevel 1
      Abort
    ${EndIf}
    Return
  ${EndIf}
  SetOutPath "$INSTDIR\installer-support"
  File /oname=.soai-launcher.pending "${PAYLOAD_DIR}\soai.exe"
  ${If} ${Errors}
    SetErrorLevel 1
    Abort
  ${EndIf}
  System::Call 'kernel32::CreateFile(t "$INSTDIR\installer-support\.soai-launcher.pending", i 0x40000000, i 1, p 0, i 3, i 0x80, p 0) p .r0'
  ${If} $0 == -1
    SetErrorLevel 1
    Abort
  ${EndIf}
  System::Call 'kernel32::FlushFileBuffers(p r0) i .r1'
  System::Call 'kernel32::CloseHandle(p r0) i .r2'
  ${If} $1 == 0
  ${OrIf} $2 == 0
    SetErrorLevel 1
    Abort
  ${EndIf}
  System::Call 'kernel32::MoveFileEx(t "$INSTDIR\installer-support\.soai-launcher.pending", t "$INSTDIR\soai.exe", i 9) i .r0'
  ${If} $0 == 0
    SetErrorLevel 1
    Abort
  ${EndIf}
  SetOutPath "$INSTDIR"
FunctionEnd
Function PrepareExistingInstallRoot
  IfFileExists "$INSTDIR\.soai-install-root" has_existing
  IfFileExists "$INSTDIR\soai.exe" has_existing
  System::Call 'kernel32::GetFileAttributes(t "$INSTDIR") i .r0 ?e'
  Pop $1
  ${If} $0 == -1
    ${If} $1 == 2
    ${OrIf} $1 == 3
      Goto done
    ${EndIf}
    Goto unrecognized_target
  ${EndIf}
  Push "$INSTDIR"
  Call InspectInstallerDirectory
  Pop $0
  ${If} $0 == "empty"
    Goto done
  ${EndIf}
  unrecognized_target:
    DetailPrint "The selected folder is not empty or could not be verified as a safe installation target."
    SetErrorLevel 1
    ${IfNot} ${Silent}
      MessageBox MB_ICONSTOP|MB_OK "Setup could not verify the selected folder. Choose an empty folder or repair the existing SoAI installation. Existing files have been retained."
    ${EndIf}
    Abort

  has_existing:
    SetOutPath "$TEMP"
    Call PreserveExistingInstallRoot
    DetailPrint "Cleaning files from the previous SoAI installation..."
    nsExec::ExecToLog '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "$PLUGINSDIR\Remove-SoAI.ps1" -InstallRoot "$INSTDIR" -Mode Upgrade'
    Pop $0
    ${If} $0 != 0
      ${If} $UpgradePrepared == 1
        Call RestoreExistingInstallRoot
      ${EndIf}
      ${IfNot} ${Silent}
        MessageBox MB_ICONSTOP|MB_OK "The previous SoAI installation could not be cleaned. Close SoAI, wait for any previous setup window to finish, and run this installer again."
      ${EndIf}
      Abort
    ${EndIf}
  done:
FunctionEnd
Function PreserveExistingInstallRoot
  GetTempFileName $UpgradeBackupRoot "$TEMP"
  Delete "$UpgradeBackupRoot"
  StrCpy $UpgradeBackupRoot "$UpgradeBackupRoot-SoAI-Upgrade-${PRODUCT_VERSION}"
  CreateDirectory "$UpgradeBackupRoot"
  DetailPrint "Preserving the current SoAI application files for rollback..."
  nsExec::ExecToLog '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "$PLUGINSDIR\Preserve-SoAIUpgrade.ps1" -InstallRoot "$INSTDIR" -BackupRoot "$UpgradeBackupRoot" -Mode Backup'
  Pop $0
  ${If} $0 != 0
    RMDir /r "$UpgradeBackupRoot"
    StrCpy $UpgradeBackupRoot ""
    ${IfNot} ${Silent}
      MessageBox MB_ICONSTOP|MB_OK "The current SoAI installation could not be preserved for rollback. Setup has not changed it."
    ${EndIf}
    Abort
  ${EndIf}
  StrCpy $UpgradePrepared 1
FunctionEnd
Function RestoreExistingInstallRoot
  DetailPrint "Restoring the previous SoAI application files..."
  nsExec::ExecToLog '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "$PLUGINSDIR\Preserve-SoAIUpgrade.ps1" -InstallRoot "$INSTDIR" -BackupRoot "$UpgradeBackupRoot" -Mode Restore -CandidateManifestPath "$PLUGINSDIR\installed-files.txt"'
  Pop $0
  ${If} $0 == 0
    Call CleanupUpgradeBackup
    ${If} $UpgradePrepared == 0
      StrCpy $UpgradeRollbackCompleted 1
    ${EndIf}
  ${Else}
    SetErrorLevel 1
  ${EndIf}
FunctionEnd
Function CleanupUpgradeBackup
  ${If} $UpgradePrepared != 1
    Return
  ${EndIf}
  nsExec::ExecToLog '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "$PLUGINSDIR\Preserve-SoAIUpgrade.ps1" -InstallRoot "$INSTDIR" -BackupRoot "$UpgradeBackupRoot" -Mode Cleanup'
  Pop $0
  ${If} $0 == 0
    StrCpy $UpgradePrepared 0
    StrCpy $UpgradeBackupRoot ""
  ${Else}
    SetErrorLevel 1
  ${EndIf}
FunctionEnd
Function CleanupFailedFreshInstall
  nsExec::ExecToLog '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "$PLUGINSDIR\Remove-SoAI.ps1" -InstallRoot "$INSTDIR" -Mode Uninstall -ManifestPath "$PLUGINSDIR\installed-files.txt"'
  Pop $0
  ${If} $0 == 0
    StrCpy $InstallMutationStarted 0
  ${EndIf}
FunctionEnd
Function LaunchSoAIFromFinish
  Exec '"$INSTDIR\soai.exe"'
FunctionEnd
