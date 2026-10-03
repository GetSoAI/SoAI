; SoAI - Windows installer lifecycle [tools/windows-release/installer/includes/InstallLifecycle.nsh]
; SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

!define SOAI_RESTORE_UPGRADE_COMMAND '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "$PLUGINSDIR\Preserve-SoAIUpgrade.ps1" -InstallRoot "$INSTDIR" -BackupRoot "$UpgradeBackupRoot" -Mode Restore -CandidateManifestPath "$PLUGINSDIR\installed-files.txt" -ControlLauncherPath "$PLUGINSDIR\soai-control.exe"'
!define SOAI_CLEANUP_UPGRADE_BACKUP_COMMAND '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "$PLUGINSDIR\Preserve-SoAIUpgrade.ps1" -InstallRoot "$INSTDIR" -BackupRoot "$UpgradeBackupRoot" -Mode Cleanup'
!define SOAI_REMOVE_FAILED_INSTALL_COMMAND '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "$PLUGINSDIR\Remove-SoAI.ps1" -InstallRoot "$INSTDIR" -Mode Uninstall -ControlLauncherPath "$PLUGINSDIR\soai-control.exe" -ManifestPath "$PLUGINSDIR\installed-files.txt" -RemoveApplicationData -InstallerRollback'

!macro RemoveInstallerDataSkeleton PREFIX
  System::Call 'kernel32::DeleteFileW(w "$InstallerFilesystemRoot\data\locks\soai.installation.transaction.lock")'
  !insertmacro TryRemoveInstallerDirectory "${PREFIX}" "$INSTDIR\data\state\locks"
  !insertmacro TryRemoveInstallerDirectory "${PREFIX}" "$INSTDIR\data\state"
  !insertmacro TryRemoveInstallerDirectory "${PREFIX}" "$INSTDIR\data\locks"
  !insertmacro TryRemoveInstallerDirectory "${PREFIX}" "$INSTDIR\data"
!macroend

!macro TryRemoveInstallerDirectory PREFIX PATH
  Push "${PATH}"
  Call ${PREFIX}RemoveInstallerDirectory
  Pop $0
!macroend

Function .onInit
  StrCpy $InstallFailed 0
  StrCpy $InstallCanceled 0
  StrCpy $InstallFailureMessage ""
  StrCpy $InstallFailureSummary ""
  StrCpy $InstallRecoveryCompleted 0
  StrCpy $InstallMutationReverted 0
  StrCpy $InstallerCreatedRoot ""
  StrCpy $InstallerDiagnosticsRetained 0
  StrCpy $UpgradeFilesRestored 0
  StrCpy $IntegrationStage 0
  StrCpy $RuntimePrepPhase ""
  StrCpy $RuntimeTaskState ""
  StrCpy $RuntimeAbortPrompt 0
  StrCpy $FinishPageTitle "Completing SoAI Setup"
  StrCpy $FinishPageText "SoAI has been installed on your computer.$\r$\n$\r$\nClick Finish to close Setup."
  StrCpy $InstFilesHeaderText "SoAI Files Installed"
  StrCpy $InstFilesHeaderSubtext "Setup will now prepare SoAI for first start."
  Call AdmitInstallerProcess
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
  ${Else}
    Call PreflightInstallerLongPaths
  ${EndIf}
FunctionEnd
Function ValidateUpdateStageRoot
  System::Call 'kernel32::GetFullPathNameW(w "$UpdateStageRoot",i ${NSIS_MAX_STRLEN},w .r0,p 0) i .r1'
  ${If} $1 == 0
  ${OrIf} $1 >= ${NSIS_MAX_STRLEN}
    SetErrorLevel 1
    Abort
  ${EndIf}
  StrCpy $UpdateStageRoot $0
  Push "$UpdateStageRoot"
  Call InstallerFilesystemPath
  Pop $0
  StrLen $0 "$0"
  IntOp $0 $0 + ${PAYLOAD_MAX_RELATIVE_LENGTH}
  IntOp $0 $0 + 2
  ${If} $0 > ${NSIS_MAX_STRLEN}
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
    Push $2
    Call InstallerFilesystemPath
    Pop $3
    System::Call 'kernel32::GetFileAttributesW(w r3) i .r0'
    ${If} $0 == -1
      SetErrorLevel 1
      Abort
    ${EndIf}
    IntOp $1 $0 & 0x410
    ${If} $1 <> 0x10
      SetErrorLevel 1
      Abort
    ${EndIf}
    ${GetRoot} "$2" $1
    ${If} $2 == "$1"
    ${OrIf} $2 == "$1\"
      Goto stage_ancestors_validated
    ${EndIf}
    ${GetParent} "$2" $1
    ${If} $1 != ""
    ${AndIf} $1 != "$2"
      StrCpy $2 "$1"
      Goto stage_parent
    ${EndIf}
  stage_ancestors_validated:
  Push "$UpdateStageRoot"
  Call RetainInstallerAncestors
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
  Push $0
  Call InstallerFilesystemPath
  Pop $0
  System::Call 'kernel32::GetFileAttributesW(w r0) i .r1'
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
Function BeginInstallation
  System::Call 'kernel32::GetTickCount64() l .r0'
  StrCpy $InstallStartTicks $0
  InitPluginsDir
  System::Call 'kernel32::DeleteFileW(w "$PLUGINSDIR\${SOAI_FAILURE_REASON_FILE}")'
  System::Call 'kernel32::SetEnvironmentVariableW(w "SOAI_INSTALLER_FAILURE_PATH",w "$PLUGINSDIR\${SOAI_FAILURE_REASON_FILE}") i .r0'
FunctionEnd
Function .onInstFailed
  ${If} $InstallFailed != 1
    StrCpy $InstallFailed 1
    StrCpy $InstallFailureMessage "Setup could not finish copying the SoAI files to $INSTDIR."
    SetErrorLevel 1
  ${EndIf}
  Call RecoverFailedInstallation
  Call WriteInstallDetailsLog
  ${IfNot} ${Silent}
    MessageBox MB_ICONSTOP|MB_OK "$InstallFailureSummary"
  ${EndIf}
FunctionEnd
Function .onInstSuccess
  ${If} $InstallFailed == 1
    Return
  ${EndIf}
  Call ReleaseInstallerPayloadDirectories
  ${If} ${Silent}
    Call CleanupUpgradeBackup
  ${EndIf}
  Call ReleaseInstallerTarget
  Call MarkInstallerDiagnosticsDisposable
FunctionEnd
Function .onGUIEnd
  ${If} $InstallerDiagnosticsRetained != 1
    Call MarkInstallerDiagnosticsDisposable
  ${EndIf}
FunctionEnd
Function AbortSoAIInstall
  ${If} $RuntimePrepPhase == ""
    MessageBox MB_YESNO|MB_ICONEXCLAMATION|MB_DEFBUTTON2 "Are you sure you want to quit SoAI Setup?" IDYES quit_setup
    Abort
    quit_setup:
    Return
  ${EndIf}
  ${If} $RuntimePrepPhase == "prepare"
  ${AndIf} $RuntimeTaskState == "running"
    StrCpy $RuntimeAbortPrompt 1
    ${If} $UpgradePrepared == 1
      StrCpy $0 "Setup will stop and restore the previous SoAI installation."
    ${Else}
      StrCpy $0 "Setup will stop and remove the incomplete installation."
    ${EndIf}
    MessageBox MB_YESNO|MB_ICONEXCLAMATION|MB_DEFBUTTON2 "Are you sure you want to cancel the SoAI installation?$\r$\n$\r$\n$0" IDNO keep_preparing
    ${If} $RuntimePrepPhase == "prepare"
    ${AndIf} $RuntimeTaskState == "running"
      Call CancelRuntimePreparation
    ${EndIf}
    keep_preparing:
    StrCpy $RuntimeAbortPrompt 0
  ${EndIf}
  Abort
FunctionEnd
Function RecoverFailedInstallation
  ${If} $InstallRecoveryCompleted == 1
    Return
  ${EndIf}
  SetDetailsPrint both
  Call BeginInstallationRecovery
  ${If} $UpgradePrepared == 1
    Call RestoreExistingInstallRoot
  ${ElseIf} $InstallMutationStarted == 1
    Call CleanupFailedFreshInstall
  ${EndIf}
  Call FinishInstallationRecovery
FunctionEnd
Function BeginInstallationRecovery
  SetOutPath "$TEMP"
  Call ReleaseInstallerPayloadDirectories
  Call RevertWindowsIntegration
FunctionEnd
Function FinishInstallationRecovery
  Call ReleaseInstallerTarget
  Call RemoveFreshInstallSkeleton
  StrCpy $InstallRecoveryCompleted 1
  Call ComposeInstallFailurePage
FunctionEnd
Function RemoveFreshInstallSkeleton
  ${If} $InstallerTargetClassification != "fresh"
  ${OrIf} $InstallMutationStarted == 1
  ${OrIf} $InstallerFilesystemRoot == ""
    Return
  ${EndIf}
  Push $0
  Push $1
  Push $2
  !insertmacro RemoveInstallerDataSkeleton ""
  StrCpy $0 "$INSTDIR"
  StrLen $1 "$InstallerCreatedRoot"
  remove_created_directory:
    ${If} $1 == 0
      Goto skeleton_removed
    ${EndIf}
    StrCpy $2 $0 $1
    ${If} $2 != $InstallerCreatedRoot
      Goto skeleton_removed
    ${EndIf}
    StrCpy $2 $0 1 $1
    ${If} $2 != ""
    ${AndIf} $2 != "\"
      Goto skeleton_removed
    ${EndIf}
    Push $0
    Call RemoveInstallerDirectory
    Pop $2
    ${If} $2 != 1
    ${OrIf} $0 == $InstallerCreatedRoot
      Goto skeleton_removed
    ${EndIf}
    ${GetParent} "$0" $0
    Goto remove_created_directory
  skeleton_removed:
  Pop $2
  Pop $1
  Pop $0
FunctionEnd
Function ComposeInstallFailurePage
  ${If} $InstallFailed != 1
    Return
  ${EndIf}
  Push $0
  Push $1
  StrCpy $InstallerDiagnosticsRetained 1
  ${If} $UpgradeFilesRestored == 1
    StrCpy $0 "The previous SoAI installation was restored, and user data was kept."
    ${If} $UpgradePrepared == 0
    ${AndIf} $InstallCanceled == 1
      StrCpy $InstallerDiagnosticsRetained 0
    ${EndIf}
  ${ElseIf} $UpgradePrepared == 1
    StrCpy $0 "Setup could not fully restore the previous SoAI installation. Restart Windows before running Setup again. User data was not removed."
  ${ElseIf} $InstallerTargetClassification == "existing"
    StrCpy $0 "The existing SoAI installation was not changed."
    ${If} $InstallCanceled == 1
      StrCpy $InstallerDiagnosticsRetained 0
    ${EndIf}
  ${ElseIf} $InstallMutationStarted == 1
    StrCpy $0 "Setup could not fully remove the incomplete installation from $INSTDIR. Restart Windows, then run Setup again."
  ${ElseIf} $InstallMutationReverted == 1
    StrCpy $0 "Setup removed the incomplete installation."
    ${If} $InstallCanceled == 1
      StrCpy $InstallerDiagnosticsRetained 0
    ${EndIf}
  ${Else}
    StrCpy $0 "No changes were made to your computer."
    ${If} $InstallCanceled == 1
      StrCpy $InstallerDiagnosticsRetained 0
    ${EndIf}
  ${EndIf}
  StrCpy $1 "$InstallFailureMessage$\r$\n$\r$\n$0"
  ${If} $InstallerDiagnosticsRetained == 1
  ${AndIf} $InstallerIsRefreshWorker == 1
    StrCpy $1 "$1$\r$\n$\r$\nDiagnostic logs were kept in:$\r$\n$InstallerPreflightRoot"
  ${EndIf}
  StrCpy $InstallFailureSummary $1
  StrCpy $FinishPageText "$1$\r$\n$\r$\nClick Finish to close Setup."
  ${If} $InstallCanceled == 1
    StrCpy $FinishPageTitle "SoAI Installation Canceled"
  ${Else}
    StrCpy $FinishPageTitle "SoAI Installation Failed"
  ${EndIf}
  StrCpy $InstFilesHeaderText "Installation Failed"
  StrCpy $InstFilesHeaderSubtext "Setup could not install SoAI."
  Pop $1
  Pop $0
FunctionEnd
Function FinishPageShow
  GetDlgItem $0 $HWNDPARENT 3
  EnableWindow $0 0
  ${If} $InstallFailed != 1
    Return
  ${EndIf}
  SendMessage $mui.FinishPage.Run ${BM_SETCHECK} ${BST_UNCHECKED} 0
  EnableWindow $mui.FinishPage.Run 0
  ShowWindow $mui.FinishPage.Run ${SW_HIDE}
  System::Call '*(i 0,i 0,i 195,i 130) p .r0'
  System::Call 'user32::MapDialogRect(p $mui.FinishPage,p r0) i .r1'
  System::Call '*$0(i,i,i .r2,i .r3)'
  System::Free $0
  ${If} $1 != 0
    System::Call 'user32::SetWindowPos(p $mui.FinishPage.Text,p 0,i 0,i 0,i r2,i r3,i 0x16)'
  ${EndIf}
  ${NSD_AddStyle} $mui.FinishPage.Text ${SS_NOPREFIX}|${SS_EDITCONTROL}
  ${NSD_SetText} $mui.FinishPage.Text "$FinishPageText"
FunctionEnd
Function MarkInstallerDiagnosticsDisposable
  ${If} $InstallerIsRefreshWorker == 1
  ${AndIf} $InstallerPreflightRoot != ""
    ClearErrors
    FileOpen $0 "$InstallerPreflightRoot\${SOAI_DISPOSABLE_DIAGNOSTICS_MARKER}" w
    ${IfNot} ${Errors}
      FileClose $0
    ${EndIf}
  ${EndIf}
FunctionEnd
Function WriteInstallDetailsLog
  ${If} ${Silent}
  ${OrIf} $InstallerIsRefreshWorker != 1
    Return
  ${EndIf}
  Push $0
  Push $1
  Push $2
  Push $3
  Push $4
  Push $5
  Push $6
  FindWindow $0 "#32770" "" $HWNDPARENT
  GetDlgItem $0 $0 1016
  ${If} $0 == 0
    Goto details_written
  ${EndIf}
  ClearErrors
  FileOpen $1 "$InstallerPreflightRoot\install-details.log" w
  ${If} ${Errors}
    Goto details_written
  ${EndIf}
  FileWriteUTF16LE /BOM $1 ""
  SendMessage $0 ${LVM_GETITEMCOUNT} 0 0 $2
  IntOp $3 ${NSIS_MAX_STRLEN} * 2
  System::Alloc $3
  Pop $3
  System::Call '*(i 0,i 0,i 0,i 0,i 0,p r3,i ${NSIS_MAX_STRLEN},i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0) p .r4'
  StrCpy $5 0
  details_line:
    ${If} $5 < $2
      System::Call 'user32::SendMessageW(p r0,i ${LVM_GETITEMTEXTW},i r5,p r4) i .r6'
      System::Call '*$3(&w${NSIS_MAX_STRLEN} .r6)'
      FileWriteUTF16LE $1 "$6$\r$\n"
      IntOp $5 $5 + 1
      Goto details_line
    ${EndIf}
  System::Free $4
  System::Free $3
  FileClose $1
  details_written:
  Pop $6
  Pop $5
  Pop $4
  Pop $3
  Pop $2
  Pop $1
  Pop $0
FunctionEnd
Function un.onInit
  Call un.AdmitInstallerProcess
  SetShellVarContext all
  SetRegView 64
  ReadRegStr $0 HKLM "${PRODUCT_REGKEY}" "InstallDir"
  ${If} $0 != ""
    StrCpy $INSTDIR "$0"
  ${Else}
    StrCpy $INSTDIR "$EXEDIR"
  ${EndIf}
  StrCpy $UninstallRemoveData 0
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/REMOVEAPPDATA" $1
  ${IfNot} ${Errors}
    StrCpy $UninstallRemoveData 1
  ${EndIf}
FunctionEnd
Function un.UninstallOptionsPageCreate
  IfSilent 0 +2
    Abort
  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}
  ${NSD_CreateLabel} 0u 0u 100% 28u "Choose whether the application data stored inside this SoAI installation should also be removed."
  Pop $0
  ${NSD_CreateCheckbox} 0u 38u 100% 28u "Remove all SoAI application data, including accounts, configuration, chats, models, files, logs, and backups"
  Pop $UninstallRemoveDataCheckbox
  ${If} $UninstallRemoveData == 1
    ${NSD_Check} $UninstallRemoveDataCheckbox
  ${EndIf}
  nsDialogs::Show
FunctionEnd
Function un.UninstallOptionsPageLeave
  ${NSD_GetState} $UninstallRemoveDataCheckbox $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $UninstallRemoveData 1
  ${Else}
    StrCpy $UninstallRemoveData 0
  ${EndIf}
FunctionEnd
Function StopExistingSoAI
  IfFileExists "$INSTDIR\soai.exe" 0 done
    DetailPrint "Stopping any running SoAI instance..."
    nsExec::ExecToLog '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "$PLUGINSDIR\Remove-SoAI.ps1" -InstallRoot "$INSTDIR" -Mode Stop -ControlLauncherPath "$PLUGINSDIR\soai-control.exe"'
    Pop $0
    ${If} $0 != 0
      !insertmacro FailInstallerScript "" "SoAI could not be stopped safely" "Close SoAI and run Setup again."
    ${EndIf}
  done:
FunctionEnd
Function StartUpdateProgressWindow
  FindFirst $0 $1 "$INSTDIR\.soai_update_transaction_*"
  FindClose $0
  ${If} $1 == ""
    Return
  ${EndIf}
  StrCpy $2 "$INSTDIR\data\state\update-progress"
  ClearErrors
  CreateDirectory "$2"
  SetOutPath "$2"
  SetOverwrite try
  File /oname=soai.exe "${PAYLOAD_DIR}\soai.exe"
  File /oname=soai.exe.config "${PAYLOAD_DIR}\soai.exe.config"
  File /oname=Microsoft.Web.WebView2.Core.dll "${PAYLOAD_DIR}\Microsoft.Web.WebView2.Core.dll"
  File /oname=Microsoft.Web.WebView2.WinForms.dll "${PAYLOAD_DIR}\Microsoft.Web.WebView2.WinForms.dll"
  File /oname=soai-app.ico "${PAYLOAD_DIR}\soai-app.ico"
  File /oname=soai-logo-dark.png "${PAYLOAD_DIR}\frontend\assets\img\soai\soai-logo-dark.png"
  File /oname=soai-logo-light.png "${PAYLOAD_DIR}\frontend\assets\img\soai\soai-logo-light.png"
  SetOverwrite on
  ${If} ${Errors}
    DetailPrint "The update progress window could not be prepared; the update continues without it."
    Return
  ${EndIf}
  Exec '"$2\soai.exe" --soai-update-progress "$INSTDIR" "${PRODUCT_VERSION}"'
FunctionEnd
Function PrepareInstallerTransactionTools
  InitPluginsDir
  SetOutPath "$PLUGINSDIR"
  ClearErrors
  SetOverwrite try
  File /oname=Remove-SoAI.ps1 "${PAYLOAD_DIR}\installer-support\Remove-SoAI.ps1"
  File /oname=soai-control.exe "${PAYLOAD_DIR}\soai.exe"
  File /oname=Preserve-SoAIUpgrade.ps1 "${PAYLOAD_DIR}\installer-support\Preserve-SoAIUpgrade.ps1"
  File /oname=installed-files.txt "${PAYLOAD_DIR}\installer-support\installed-files.txt"
  SetOverwrite on
  ${If} ${Errors}
    !insertmacro FailInstallerStep "" "Setup could not prepare its installation tools in $PLUGINSDIR."
  ${EndIf}
FunctionEnd
!define SOAI_LAUNCHER_INSTALL_FAILURE "Setup could not install the SoAI launcher in $INSTDIR."
Function InstallCandidateLauncher
  ClearErrors
  DetailPrint "Extract: soai.exe"
  SetDetailsPrint none
  SetOverwrite try
  ${If} $UpdateStageRoot != ""
    Push "$INSTDIR"
    Call InstallerFilesystemPath
    Pop $0
    File "/oname=$0\soai.exe" "${PAYLOAD_DIR}\soai.exe"
    SetDetailsPrint both
    ${If} ${Errors}
      !insertmacro FailInstallerStep "" "${SOAI_LAUNCHER_INSTALL_FAILURE}"
    ${EndIf}
    Return
  ${EndIf}
  File "/oname=$InstallerFilesystemRoot\installer-support\.soai-launcher.pending" "${PAYLOAD_DIR}\soai.exe"
  SetOverwrite on
  SetDetailsPrint both
  ${If} ${Errors}
    !insertmacro FailInstallerStep "" "${SOAI_LAUNCHER_INSTALL_FAILURE}"
  ${EndIf}
  System::Call 'kernel32::CreateFile(w "$InstallerFilesystemRoot\installer-support\.soai-launcher.pending", i 0x40000000, i 1, p 0, i 3, i 0x80, p 0) p .r0'
  ${If} $0 == -1
    !insertmacro FailInstallerStep "" "${SOAI_LAUNCHER_INSTALL_FAILURE}"
  ${EndIf}
  System::Call 'kernel32::FlushFileBuffers(p r0) i .r1'
  System::Call 'kernel32::CloseHandle(p r0) i .r2'
  ${If} $1 == 0
  ${OrIf} $2 == 0
    !insertmacro FailInstallerStep "" "${SOAI_LAUNCHER_INSTALL_FAILURE}"
  ${EndIf}
  System::Call 'kernel32::MoveFileEx(w "$InstallerFilesystemRoot\installer-support\.soai-launcher.pending", w "$InstallerFilesystemRoot\soai.exe", i 9) i .r0'
  ${If} $0 == 0
    !insertmacro FailInstallerStep "" "${SOAI_LAUNCHER_INSTALL_FAILURE}"
  ${EndIf}
  System::Call 'kernel32::CopyFileW(w "$InstallerFilesystemRoot\installer-support\soai.exe.config", w "$InstallerFilesystemRoot\installer-support\.soai-launcher-config.pending", i 1) i .r0'
  ${If} $0 == 0
    !insertmacro FailInstallerStep "" "${SOAI_LAUNCHER_INSTALL_FAILURE}"
  ${EndIf}
  System::Call 'kernel32::CreateFileW(w "$InstallerFilesystemRoot\installer-support\.soai-launcher-config.pending",i 0x40000000,i 1,p 0,i 3,i 0x80,p 0) p .r0'
  ${If} $0 == -1
    !insertmacro FailInstallerStep "" "${SOAI_LAUNCHER_INSTALL_FAILURE}"
  ${EndIf}
  System::Call 'kernel32::FlushFileBuffers(p r0) i .r1'
  System::Call 'kernel32::CloseHandle(p r0) i .r2'
  ${If} $1 == 0
  ${OrIf} $2 == 0
    !insertmacro FailInstallerStep "" "${SOAI_LAUNCHER_INSTALL_FAILURE}"
  ${EndIf}
  System::Call 'kernel32::MoveFileExW(w "$InstallerFilesystemRoot\installer-support\.soai-launcher-config.pending",w "$InstallerFilesystemRoot\soai.exe.config",i 9) i .r0'
  ${If} $0 == 0
    !insertmacro FailInstallerStep "" "${SOAI_LAUNCHER_INSTALL_FAILURE}"
  ${EndIf}
FunctionEnd
Function PrepareExistingInstallRoot
  ${If} $InstallerTargetClassification == "fresh"
    Return
  ${EndIf}
  ${If} $InstallerTargetClassification != "existing"
    !insertmacro FailInstallerStep "" "Setup could not classify the installation folder $INSTDIR."
  ${EndIf}
  SetOutPath "$TEMP"
  Call PreserveExistingInstallRoot
  ${If} $InstallFailed == 1
    Return
  ${EndIf}
  DetailPrint "Cleaning files from the previous SoAI installation..."
  nsExec::ExecToLog '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "$PLUGINSDIR\Remove-SoAI.ps1" -InstallRoot "$INSTDIR" -Mode Upgrade -ControlLauncherPath "$PLUGINSDIR\soai-control.exe"'
  Pop $0
  ${If} $0 != 0
    !insertmacro FailInstallerScript "" "The previous SoAI installation could not be cleaned" "Close SoAI, wait for any previous setup window to finish, and run Setup again."
  ${EndIf}
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
    !insertmacro FailInstallerScript "" "The current SoAI installation could not be preserved for rollback" "Setup has not changed it."
  ${EndIf}
  StrCpy $UpgradePrepared 1
FunctionEnd
Function RestoreExistingInstallRoot
  DetailPrint "Restoring the previous SoAI application files..."
  nsExec::ExecToLog '${SOAI_RESTORE_UPGRADE_COMMAND}'
  Pop $0
  Call CompleteUpgradeRestore
  ${If} $0 == 0
    Call CleanupUpgradeBackup
  ${EndIf}
FunctionEnd
Function CompleteUpgradeRestore
  ${If} $0 == 0
    StrCpy $UpgradeFilesRestored 1
  ${Else}
    SetErrorLevel 1
  ${EndIf}
FunctionEnd
Function CleanupUpgradeBackup
  ${If} $UpgradePrepared != 1
    Return
  ${EndIf}
  nsExec::ExecToLog '${SOAI_CLEANUP_UPGRADE_BACKUP_COMMAND}'
  Pop $0
  Call CompleteUpgradeBackupCleanup
FunctionEnd
Function CompleteUpgradeBackupCleanup
  ${If} $0 == 0
    StrCpy $UpgradePrepared 0
    StrCpy $UpgradeBackupRoot ""
  ${Else}
    SetErrorLevel 1
  ${EndIf}
FunctionEnd
Function CleanupFailedFreshInstall
  DetailPrint "Removing the incomplete SoAI installation..."
  nsExec::ExecToLog '${SOAI_REMOVE_FAILED_INSTALL_COMMAND}'
  Pop $0
  Call CompleteFailedFreshInstallCleanup
FunctionEnd
Function CompleteFailedFreshInstallCleanup
  ${If} $0 == 0
    StrCpy $InstallMutationStarted 0
    StrCpy $InstallMutationReverted 1
  ${Else}
    SetErrorLevel 1
  ${EndIf}
FunctionEnd
Function LaunchSoAIFromFinish
  ${If} $InstallFailed == 1
    Return
  ${EndIf}
  ${If} $InstallerIsRefreshWorker == 1
    ClearErrors
    FileOpen $0 "$InstallerRefreshResultRoot\launch-root.txt" w
    FileWrite $0 "$INSTDIR"
    FileClose $0
    ${If} ${Errors}
      SetErrorLevel 1
    ${EndIf}
    Return
  ${EndIf}
  Exec '"$INSTDIR\soai.exe"'
FunctionEnd
