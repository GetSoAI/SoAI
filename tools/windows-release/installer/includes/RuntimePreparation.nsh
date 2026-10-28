; SoAI - Windows installer runtime preparation [tools/windows-release/installer/includes/RuntimePreparation.nsh]
; SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

!define SOAI_RUNTIME_PREPARATION_COMMAND '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -NonInteractive -File "$RuntimeWrapperPath" -InstallRoot "$INSTDIR" -DiagnosticRoot "$RuntimeDiagnosticPath"$RuntimeExistingInstallationArgument'
!define SOAI_RUNTIME_PREPARATION_LIMIT_SECONDS 14400
!define SOAI_RUNTIME_TASK_STOP_SECONDS 30

Function SetInstallerProgress
  Exch $0
  Push $1
  ${If} $RuntimePageProgress != ""
    StrCpy $1 $RuntimePageProgress
  ${Else}
    GetDlgItem $1 $HWNDPARENT 1004
  ${EndIf}
  SendMessage $1 ${PBM_SETRANGE32} 0 100
  SendMessage $1 ${PBM_SETPOS} $0 0
  Pop $1
  Pop $0
FunctionEnd
Function CreateRuntimePrepWrapper
  StrCpy $RuntimeDiagnosticPath "$InstallerPreflightRoot\runtime"
  System::Call 'kernel32::CreateDirectoryW(w "$RuntimeDiagnosticPath",p 0) i .r0'
  ${If} $0 == 0
    !insertmacro FailInstallerStep "" "Setup could not create its runtime diagnostics folder $RuntimeDiagnosticPath."
  ${EndIf}
  StrCpy $RuntimeStatusPath "$RuntimeDiagnosticPath\install-status.ini"
  StrCpy $RuntimeExitPath "$RuntimeDiagnosticPath\install-exit-code.txt"
  StrCpy $RuntimeErrorPath "$RuntimeDiagnosticPath\install-error.txt"
  StrCpy $RuntimeWrapperPath "$RuntimeDiagnosticPath\run-install-runtime.ps1"
  StrCpy $RuntimeExistingInstallationArgument ""
  ${If} $InstallerTargetClassification == "existing"
    StrCpy $RuntimeExistingInstallationArgument " -ExistingInstallation"
  ${EndIf}
  ClearErrors
  FileOpen $0 "$RuntimeWrapperPath" w
  FileWrite $0 "param([string]$$InstallRoot, [string]$$DiagnosticRoot, [switch]$$ExistingInstallation)$\r$\n"
  FileWrite $0 "$$ErrorActionPreference = 'Stop'$\r$\n"
  FileWrite $0 "$$exitCode = 0$\r$\n"
  FileWrite $0 "[IO.File]::WriteAllText((Join-Path $$DiagnosticRoot 'install-root.txt'), $$InstallRoot, [Text.Encoding]::Unicode)$\r$\n"
  FileWrite $0 "try {$\r$\n"
  FileWrite $0 "  & (Join-Path $$InstallRoot 'installer-support\Install-SoAIRuntime.ps1') -InstallRoot $$InstallRoot -PythonVersion '${PYTHON_VERSION}' -PythonUrl '${PYTHON_URL}' -PythonSha256 '${PYTHON_SHA256}' -WebView2BootstrapperUrl '${WEBVIEW2_BOOTSTRAPPER_URL}' -DiagnosticRoot (Join-Path $$DiagnosticRoot 'logs') -StatusPath (Join-Path $$DiagnosticRoot 'install-status.ini') -ExistingInstallation:$$ExistingInstallation$\r$\n"
  FileWrite $0 "  Add-Type -AssemblyName System.IO.Compression.FileSystem$\r$\n"
  FileWrite $0 "  $$nativeRoot = if ($$InstallRoot.StartsWith('\\')) { '\\?\UNC\' + $$InstallRoot.Substring(2) } else { '\\?\' + $$InstallRoot }$\r$\n"
  FileWrite $0 "  $$identity = [IO.Path]::GetFileName([IO.Path]::GetDirectoryName($$DiagnosticRoot))$\r$\n"
  FileWrite $0 "  [IO.Compression.ZipFile]::CreateFromDirectory((Join-Path $$DiagnosticRoot 'logs'), ($$nativeRoot + '\installer-support\install-diagnostics-' + $$identity + '.zip'))$\r$\n"
  FileWrite $0 "} catch {$\r$\n"
  FileWrite $0 "  $$message = ($$_.Exception.Message -replace '[\r\n]+', ' ').Trim()$\r$\n"
  FileWrite $0 "  if ([string]::IsNullOrWhiteSpace($$message)) { $$message = 'SoAI runtime preparation failed.' }$\r$\n"
  FileWrite $0 "  Write-Host ('SoAI runtime preparation failed. Diagnostic bundle: ' + $$DiagnosticRoot)$\r$\n"
  FileWrite $0 "  Set-Content -LiteralPath (Join-Path $$DiagnosticRoot 'install-error.txt') -Value $$message -Encoding Unicode$\r$\n"
  FileWrite $0 "  $$exitCode = 1$\r$\n"
  FileWrite $0 "}$\r$\n"
  FileWrite $0 "Set-Content -LiteralPath (Join-Path $$DiagnosticRoot 'install-exit-code.txt') -Value $$exitCode -Encoding ASCII$\r$\n"
  FileWrite $0 "exit $$exitCode$\r$\n"
  FileClose $0
  ${If} ${Errors}
    !insertmacro FailInstallerStep "" "Setup could not write its runtime preparation script to $RuntimeDiagnosticPath."
  ${EndIf}
FunctionEnd
Function ComposeRuntimeFailureMessage
  Exch $0
  Push $1
  StrCpy $1 ""
  IfFileExists "$RuntimeErrorPath" 0 compose_runtime_failure
    Push "$RuntimeErrorPath"
    Call ReadInstallerReason
    Pop $1
  compose_runtime_failure:
  ${If} $1 == ""
    StrCpy $1 "SoAI runtime preparation stopped unexpectedly with exit code $0."
  ${ElseIf} $1 != "SoAI runtime preparation failed."
    Push $1
    Call FormatInstallerReason
    Pop $1
    StrCpy $1 "SoAI could not be prepared: $1"
  ${EndIf}
  Exch $1
  Exch
  Pop $0
FunctionEnd
Function RuntimePrepRunSilent
  DetailPrint "Preparing SoAI for first start..."
  Call CreateRuntimePrepWrapper
  SetOutPath "$TEMP"
  nsExec::ExecToLog '${SOAI_RUNTIME_PREPARATION_COMMAND}'
  Pop $0
  ${If} $0 != 0
    Push $0
    Call ComposeRuntimeFailureMessage
    Call RecordInstallFailure
    Return
  ${EndIf}
  RMDir /r "$RuntimeDiagnosticPath"

  Call CreateWindowsIntegration
FunctionEnd
Function GetInstallElapsedSeconds
  Push $0
  ${If} $InstallStartTicks == ""
    StrCpy $0 0
  ${Else}
    System::Call 'kernel32::GetTickCount64() l .r0'
    System::Int64Op $0 - $InstallStartTicks
    Pop $0
    System::Int64Op $0 / 1000
    Pop $0
  ${EndIf}
  Exch $0
FunctionEnd
Function StartRuntimeTask
  Exch $R0
  Exch
  Exch $R1
  Push $0
  Push $1
  Push $2
  Push $3
  Push $4
  Push $5
  Push $6
  Push $7
  Push $8
  StrCpy $RuntimeTaskState "failed"
  StrCpy $RuntimeTaskExitCode ""
  StrCpy $2 -1
  StrCpy $3 -1
  Call CreateInstallerJobObject
  Pop $0
  ${If} $0 == 0
    Goto task_started
  ${EndIf}
  System::Call '*(i 12,p 0,i 1) p .r1'
  System::Call 'kernel32::CreateFileW(w R1,i 0x4,i 7,p r1,i 4,i 0x80,p 0) p .r2'
  System::Call 'kernel32::CreateFileW(w "NUL",i 0x80000000,i 3,p r1,i 3,i 0,p 0) p .r3'
  System::Free $1
  ${If} $2 == -1
  ${OrIf} $3 == -1
    Goto task_started
  ${EndIf}
  System::Call '*(i 68,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0x101,i 0,i 0,p r3,p r2,p r2) p .r4'
  System::Call '*(p 0,p 0,i 0,i 0) p .r5'
  System::Call 'kernel32::CreateProcessW(p 0,w R0,p 0,p 0,i 1,i 0x08000004,p 0,w "$TEMP",p r4,p r5) i .r6'
  System::Free $4
  ${If} $6 == 0
    System::Free $5
    Goto task_started
  ${EndIf}
  System::Call '*$5(p .r7,p .r8,i,i)'
  System::Free $5
  System::Call 'kernel32::AssignProcessToJobObject(p r0,p r7) i .r6'
  ${If} $6 != 0
    System::Call 'kernel32::ResumeThread(p r8) i .r6'
  ${Else}
    StrCpy $6 -1
  ${EndIf}
  System::Call 'kernel32::CloseHandle(p r8)'
  ${If} $6 == -1
    System::Call 'kernel32::TerminateProcess(p r7,i 1)'
    System::Call 'kernel32::WaitForSingleObject(p r7,i 5000)'
    System::Call 'kernel32::CloseHandle(p r7)'
    Goto task_started
  ${EndIf}
  StrCpy $RuntimeProcessHandle $7
  StrCpy $RuntimeJobHandle $0
  StrCpy $0 0
  StrCpy $RuntimeTaskState "running"
  task_started:
  ${If} $2 != -1
    System::Call 'kernel32::CloseHandle(p r2)'
  ${EndIf}
  ${If} $3 != -1
    System::Call 'kernel32::CloseHandle(p r3)'
  ${EndIf}
  ${If} $0 != 0
    System::Call 'kernel32::CloseHandle(p r0)'
  ${EndIf}
  Pop $8
  Pop $7
  Pop $6
  Pop $5
  Pop $4
  Pop $3
  Pop $2
  Pop $1
  Pop $0
  Pop $R1
  Pop $R0
FunctionEnd
Function StopRuntimeTask
  ${If} $RuntimeTaskState == "running"
    ${If} $RuntimeTaskExitCode == ""
      StrCpy $RuntimeTaskExitCode 1
    ${EndIf}
    System::Call 'kernel32::TerminateJobObject(p $RuntimeJobHandle,i 1)'
    Call GetInstallElapsedSeconds
    Pop $RuntimeTaskStopSeconds
    StrCpy $RuntimeTaskState "stopping"
  ${EndIf}
FunctionEnd
Function PollRuntimeTask
  ${If} $RuntimeTaskState == "running"
    System::Call 'kernel32::WaitForSingleObject(p $RuntimeProcessHandle,i 0) i .r0'
    ${If} $0 == 258
      Return
    ${EndIf}
    StrCpy $1 1
    ${If} $0 == 0
      System::Call 'kernel32::GetExitCodeProcess(p $RuntimeProcessHandle,*i .r1) i .r2'
      ${If} $2 == 0
        StrCpy $1 1
      ${EndIf}
    ${EndIf}
    StrCpy $RuntimeTaskExitCode $1
    Call StopRuntimeTask
  ${EndIf}
  ${If} $RuntimeTaskState == "stopping"
    Push $RuntimeJobHandle
    Call CountInstallerJobProcesses
    Pop $0
    Call GetInstallElapsedSeconds
    Pop $1
    IntOp $1 $1 - $RuntimeTaskStopSeconds
    ${If} $0 == 0
    ${OrIf} $0 < 0
    ${OrIf} $1 >= ${SOAI_RUNTIME_TASK_STOP_SECONDS}
      System::Call 'kernel32::CloseHandle(p $RuntimeProcessHandle)'
      System::Call 'kernel32::CloseHandle(p $RuntimeJobHandle)'
      StrCpy $RuntimeProcessHandle 0
      StrCpy $RuntimeJobHandle 0
      StrCpy $RuntimeTaskState "exited"
    ${EndIf}
  ${EndIf}
FunctionEnd
Function StartRuntimePhaseTask
  Exch $0
  Exch
  Exch $1
  StrCpy $RuntimePrepPhase $1
  Push "$InstallerPreflightRoot\$1-output.log"
  Push $0
  Call StartRuntimeTask
  ${If} $RuntimeTaskState != "running"
    StrCpy $RuntimeTaskExitCode 1
    StrCpy $RuntimeTaskState "exited"
  ${EndIf}
  Pop $1
  Pop $0
FunctionEnd
Function SetRuntimePageText
  Exch $0
  Exch
  Exch $1
  ${If} $RuntimePageStatusLabel != ""
    ${NSD_SetText} $RuntimePageStatusLabel "$0"
    ${NSD_SetText} $RuntimePageDetailLabel "$1"
  ${EndIf}
  StrCpy $LastRuntimeStatusMessage "$0"
  StrCpy $LastRuntimeStatusDetail "$1"
  Pop $1
  Pop $0
FunctionEnd
Function RefreshRuntimeStatus
  IfFileExists "$RuntimeStatusPath" 0 status_refreshed
    ReadINIStr $1 "$RuntimeStatusPath" "status" "progress"
    ReadINIStr $2 "$RuntimeStatusPath" "status" "message"
    ReadINIStr $3 "$RuntimeStatusPath" "status" "detail"
    ${If} $1 != ""
    ${AndIf} $1 != $RuntimeCurrentProgress
      StrCpy $RuntimeCurrentProgress "$1"
      Push $RuntimeCurrentProgress
      Call SetInstallerProgress
    ${EndIf}
    ${If} $2 != ""
    ${AndIf} $2 S!= $LastRuntimeStatusMessage
      ${NSD_SetText} $RuntimePageStatusLabel "$2"
      StrCpy $LastRuntimeStatusMessage "$2"
    ${EndIf}
    ${If} $3 S!= $LastRuntimeStatusDetail
      ${NSD_SetText} $RuntimePageDetailLabel "$3"
      StrCpy $LastRuntimeStatusDetail "$3"
    ${EndIf}
  status_refreshed:
FunctionEnd
Function RefreshRuntimeElapsed
  Call GetInstallElapsedSeconds
  Pop $0
  IntOp $1 $0 / 3600
  IntOp $2 $0 % 3600
  IntOp $2 $2 / 60
  IntOp $3 $0 % 60
  IntFmt $3 "%02d" $3
  ${If} $1 > 0
    IntFmt $2 "%02d" $2
    StrCpy $0 "$1:$2:$3"
  ${Else}
    StrCpy $0 "$2:$3"
  ${EndIf}
  ${If} $0 S!= $RuntimeElapsedText
    StrCpy $RuntimeElapsedText $0
    ${NSD_SetText} $RuntimePageElapsedLabel "Elapsed time: $0"
  ${EndIf}
FunctionEnd
Function DisableRuntimePageClose
  GetDlgItem $0 $HWNDPARENT 2
  EnableWindow $0 0
  System::Call 'user32::GetSystemMenu(p $HWNDPARENT,i 0) p .r0'
  System::Call 'user32::EnableMenuItem(p r0,i 0xF060,i 1)'
FunctionEnd
Function ShowRuntimeRecoveryState
  Call DisableRuntimePageClose
  System::Call 'user32::GetWindowLongW(p $RuntimePageProgress,i -16) i .r0'
  IntOp $0 $0 | ${PBS_MARQUEE}
  System::Call 'user32::SetWindowLongW(p $RuntimePageProgress,i -16,i r0)'
  SendMessage $RuntimePageProgress ${PBM_SETMARQUEE} 1 40
  GetDlgItem $0 $HWNDPARENT 1037
  ${If} $InstallCanceled == 1
    ${NSD_SetText} $0 "Canceling SoAI Setup"
  ${Else}
    ${NSD_SetText} $0 "SoAI Setup Failed"
  ${EndIf}
  GetDlgItem $0 $HWNDPARENT 1038
  ${NSD_SetText} $0 "Setup is undoing the changes it made."
  ${NSD_SetText} $RuntimePageInfoLabel "Please wait. Setup will show the result when it has finished."
FunctionEnd
Function CancelRuntimePreparation
  StrCpy $InstallCanceled 1
  Push "You canceled the SoAI installation."
  Call RecordInstallFailure
  Call ShowRuntimeRecoveryState
  Push ""
  Push "Stopping SoAI runtime preparation..."
  Call SetRuntimePageText
  Call StopRuntimeTask
FunctionEnd
Function BeginRuntimeRecovery
  StrCpy $RuntimePrepPhase "recover"
  Call ShowRuntimeRecoveryState
  Call BeginInstallationRecovery
  ${If} $UpgradePrepared == 1
    Push ""
    Push "Restoring the previous SoAI installation..."
    Call SetRuntimePageText
    Push "restore"
    Push '${SOAI_RESTORE_UPGRADE_COMMAND}'
    Call StartRuntimePhaseTask
  ${ElseIf} $InstallMutationStarted == 1
    Push ""
    Push "Removing the incomplete SoAI installation..."
    Call SetRuntimePageText
    Push "remove"
    Push '${SOAI_REMOVE_FAILED_INSTALL_COMMAND}'
    Call StartRuntimePhaseTask
  ${Else}
    Call FinishRuntimeRecovery
  ${EndIf}
FunctionEnd
Function FinishRuntimeRecovery
  Call FinishInstallationRecovery
  Call LeaveRuntimePreparation
FunctionEnd
Function FinishRuntimePreparation
  StrCpy $RuntimePrepPhase "finalize"
  Call DisableRuntimePageClose
  Push ""
  Push "Registering SoAI with Windows..."
  Call SetRuntimePageText
  Call CreateWindowsIntegration
  ${If} $InstallFailed == 1
    Call BeginRuntimeRecovery
    Return
  ${EndIf}
  ${If} $UpgradePrepared == 1
    Call StartUpgradeBackupCleanupTask
    Return
  ${EndIf}
  Call FinishRuntimeSuccess
FunctionEnd
Function StartUpgradeBackupCleanupTask
  Push ""
  Push "Removing the temporary copy of the previous SoAI installation..."
  Call SetRuntimePageText
  Push "backup-cleanup"
  Push '${SOAI_CLEANUP_UPGRADE_BACKUP_COMMAND}'
  Call StartRuntimePhaseTask
FunctionEnd
Function FinishRuntimeSuccess
  RMDir /r "$RuntimeDiagnosticPath"
  Call ReleaseInstallerPayloadDirectories
  Call ReleaseInstallerTarget
  Push 100
  Call SetInstallerProgress
  Push ""
  Push "SoAI is ready to start."
  Call SetRuntimePageText
  Call LeaveRuntimePreparation
FunctionEnd
Function LeaveRuntimePreparation
  ${NSD_KillTimer} RuntimePrepTimer
  StrCpy $RuntimePrepPhase "done"
  System::Call 'user32::PostMessageW(p $HWNDPARENT,i 0x408,i 1,i 0)'
FunctionEnd
Function CompleteRuntimeTask
  StrCpy $RuntimeTaskState ""
  StrCpy $0 $RuntimeTaskExitCode
  ${If} $RuntimePrepPhase == "prepare"
    ${If} $InstallFailed == 1
      Call BeginRuntimeRecovery
    ${ElseIf} $RuntimePrepTimedOut == 1
      Push "SoAI runtime preparation did not finish within 4 hours."
      Call RecordInstallFailure
      Call BeginRuntimeRecovery
    ${ElseIf} $0 != 0
      Push $0
      Call ComposeRuntimeFailureMessage
      Call RecordInstallFailure
      Call BeginRuntimeRecovery
    ${Else}
      Call FinishRuntimePreparation
    ${EndIf}
  ${ElseIf} $RuntimePrepPhase == "restore"
    Call CompleteUpgradeRestore
    ${If} $0 == 0
      Call StartUpgradeBackupCleanupTask
    ${Else}
      Call FinishRuntimeRecovery
    ${EndIf}
  ${ElseIf} $RuntimePrepPhase == "remove"
    Call CompleteFailedFreshInstallCleanup
    Call FinishRuntimeRecovery
  ${ElseIf} $RuntimePrepPhase == "backup-cleanup"
    Call CompleteUpgradeBackupCleanup
    ${If} $InstallFailed == 1
      Call FinishRuntimeRecovery
    ${Else}
      Call FinishRuntimeSuccess
    ${EndIf}
  ${EndIf}
FunctionEnd
Function RuntimePrepTimer
  Call RefreshRuntimeElapsed
  ${If} $RuntimePrepPhase == "prepare"
  ${AndIf} $RuntimeTaskState == "running"
    Call RefreshRuntimeStatus
  ${EndIf}
  ${If} $RuntimeAbortPrompt == 1
    Return
  ${EndIf}
  ${If} $RuntimePrepPhase == "prepare"
  ${AndIf} $RuntimeTaskState == "running"
    Call GetInstallElapsedSeconds
    Pop $0
    IntOp $0 $0 - $RuntimePrepStartSeconds
    ${If} $0 >= ${SOAI_RUNTIME_PREPARATION_LIMIT_SECONDS}
      StrCpy $RuntimePrepTimedOut 1
      Call StopRuntimeTask
    ${EndIf}
  ${EndIf}
  Call PollRuntimeTask
  ${If} $RuntimeTaskState == "exited"
    Call CompleteRuntimeTask
  ${EndIf}
FunctionEnd
Function RuntimePrepStart
  StrCpy $LastRuntimeStatusMessage ""
  StrCpy $LastRuntimeStatusDetail ""
  StrCpy $RuntimeElapsedText ""
  StrCpy $RuntimeCurrentProgress 35
  StrCpy $RuntimePrepTimedOut 0
  Call CreateRuntimePrepWrapper
  ${If} $InstallFailed == 1
    Call BeginRuntimeRecovery
    Return
  ${EndIf}
  Call GetInstallElapsedSeconds
  Pop $RuntimePrepStartSeconds
  SetOutPath "$TEMP"
  Push "$RuntimeDiagnosticPath\runtime-output.log"
  Push '${SOAI_RUNTIME_PREPARATION_COMMAND}'
  Call StartRuntimeTask
  ${If} $RuntimeTaskState != "running"
    Push "Setup could not start SoAI runtime preparation."
    Call RecordInstallFailure
    Call BeginRuntimeRecovery
  ${EndIf}
FunctionEnd
Function RuntimePrepPageCreate
  ${If} $InstallFailed == 1
  ${OrIf} $RuntimePrepPhase != ""
    Abort
  ${EndIf}
  SetDetailsPrint none
  StrCpy $RuntimePrepPhase "prepare"
  StrCpy $RuntimePageProgress ""
  GetDlgItem $0 $HWNDPARENT 1037
  ${NSD_SetText} $0 "Preparing SoAI"
  GetDlgItem $0 $HWNDPARENT 1038
  ${NSD_SetText} $0 "Setup is downloading and preparing the components SoAI needs."

  nsDialogs::Create 1018
  Pop $RuntimePageDialog
  ${If} $RuntimePageDialog == error
    Push "Setup could not display the SoAI runtime preparation page."
    Call RecordInstallFailure
    StrCpy $RuntimePrepPhase "done"
    Call RecoverFailedInstallation
    Abort
  ${EndIf}

  ${NSD_CreateLabel} 0u 0u 100% 20u "Starting SoAI runtime preparation..."
  Pop $RuntimePageStatusLabel
  ${NSD_AddStyle} $RuntimePageStatusLabel ${SS_NOPREFIX}|${SS_EDITCONTROL}
  ${NSD_CreateProgressBar} 0u 24u 100% 12u ""
  Pop $RuntimePageProgress
  SendMessage $RuntimePageProgress ${PBM_SETRANGE32} 0 100
  SendMessage $RuntimePageProgress ${PBM_SETPOS} 35 0
  ${NSD_CreateLabel} 0u 42u 100% 28u ""
  Pop $RuntimePageDetailLabel
  ${NSD_AddStyle} $RuntimePageDetailLabel ${SS_NOPREFIX}|${SS_EDITCONTROL}
  ${NSD_CreateLabel} 0u 74u 100% 10u "Elapsed time: 0:00"
  Pop $RuntimePageElapsedLabel
  ${NSD_CreateLabel} 0u 92u 100% 40u "This can take several minutes while Setup downloads and prepares the components SoAI needs. If you cancel, Setup undoes the changes it made."
  Pop $RuntimePageInfoLabel

  GetDlgItem $0 $HWNDPARENT 1
  EnableWindow $0 0
  GetDlgItem $0 $HWNDPARENT 3
  EnableWindow $0 0

  ${NSD_CreateTimer} RuntimePrepTimer 500
  Call RuntimePrepStart
  nsDialogs::Show
FunctionEnd
Function RuntimePrepPageLeave
  ${If} $RuntimePrepPhase != "done"
    Abort
  ${EndIf}
FunctionEnd
