; SoAI - Windows installer process admission [installer/includes/InstallAdmission.nsh]
; SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

!define SOAI_DISPOSABLE_DIAGNOSTICS_MARKER "diagnostics.disposable"

!macro DefineInstallerProcessAdmission PREFIX
Function ${PREFIX}AdmitInstallerProcess
  System::Call 'kernel32::GetCommandLineW() p .r0'
  System::Call 'kernel32::lstrlenW(p r0) i .r1'
  ${If} $1 >= ${NSIS_MAX_STRLEN}
    ${IfNot} ${Silent}
      MessageBox MB_ICONSTOP|MB_OK "Setup arguments exceed the supported command-line capacity. Use a shorter installation path."
    ${EndIf}
    SetErrorLevel 1
    Abort
  ${EndIf}
  StrCpy $InstallerIsRefreshWorker 0
  ReadEnvStr $2 "SOAI_INSTALL_REFRESH_PARENT_PID"
  ${If} $2 != ""
    System::Call '*(i 0,i 0,i 0,i 0,i 0,i 0) p .r3'
    System::Call 'ntdll::NtQueryInformationProcess(p -1,i 0,p r3,i 24,*i .r4) i .r0'
    System::Call '*$3(i,i,i,i,i,i .r4)'
    System::Free $3
    ${If} $0 != 0
    ${OrIf} $4 != $2
      SetErrorLevel 1
      Abort
    ${EndIf}
    System::Call 'kernel32::OpenProcess(i 0x00101000,i 0,i r4) p .r3'
    ${If} $3 == 0
      SetErrorLevel 1
      Abort
    ${EndIf}
    StrCpy $5 ${NSIS_MAX_STRLEN}
    System::Call 'kernel32::QueryFullProcessImageNameW(p r3,i 0,w .r4,*i r5) i .r0'
    System::Call 'kernel32::WaitForSingleObject(p r3,i 0) i .r5'
    System::Call 'kernel32::CloseHandle(p r3)'
    ${If} $0 == 0
    ${OrIf} $4 != "$EXEPATH"
    ${OrIf} $5 != 258
      SetErrorLevel 1
      Abort
    ${EndIf}
    System::Call 'kernel32::OpenMutexW(i 0x00100000,i 0,w "Global\SoAI.WindowsInstaller.V1") p .r1'
    StrCpy $InstallerMutexHandle $1
    ${If} $InstallerMutexHandle == 0
      SetErrorLevel 1
      Abort
    ${EndIf}
    System::Call 'kernel32::SetEnvironmentVariableW(w "SOAI_INSTALL_REFRESH_PARENT_PID",p 0)'
    ReadEnvStr $InstallerRefreshResultRoot "SOAI_INSTALL_REFRESH_RESULT_ROOT"
    StrCpy $InstallerIsRefreshWorker 1
    Return
  ${EndIf}
  System::Call 'kernel32::CreateMutexW(p 0,i 0,w "Global\SoAI.WindowsInstaller.V1") p .r1 ?e'
  Pop $0
  StrCpy $InstallerMutexHandle $1
  ${If} $InstallerMutexHandle == 0
  ${OrIf} $0 == 183
    ${IfNot} ${Silent}
      MessageBox MB_ICONSTOP|MB_OK "Another SoAI installer or repair operation is active. Finish it before starting this installer."
    ${EndIf}
    SetErrorLevel 1
    Abort
  ${EndIf}
FunctionEnd
!macroend
!insertmacro DefineInstallerProcessAdmission ""
!insertmacro DefineInstallerProcessAdmission "un."

Function PreflightInstallerLongPaths
  ${If} $InstallerIsRefreshWorker == 1
    StrCpy $InstallerPreflightRoot "$InstallerRefreshResultRoot"
    nsExec::ExecToLog '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$InstallerPreflightRoot\Install-SoAIRuntime.ps1" -PreflightOnly'
    Pop $0
    ${If} $0 != 0
      SetErrorLevel 1
      Abort
    ${EndIf}
    Return
  ${EndIf}
  ReadRegDWORD $7 HKLM "SYSTEM\CurrentControlSet\Control\FileSystem" "LongPathsEnabled"
  System::Call '*(l 0,l 0) p .r0'
  System::Call 'ole32::CoCreateGuid(p r0) i .r1'
  System::Call 'ole32::StringFromGUID2(p r0,w .r2,i 39) i .r3'
  System::Free $0
  ${If} $1 != 0
  ${OrIf} $3 == 0
    SetErrorLevel 1
    Abort
  ${EndIf}
  StrCpy $InstallerPreflightRoot "$WINDIR\Temp\SoAI-Preflight-$2"
  System::Call 'advapi32::ConvertStringSecurityDescriptorToSecurityDescriptorW(w "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)",i 1,*p .r1,p 0) i .r2'
  ${If} $2 == 0
    SetErrorLevel 1
    Abort
  ${EndIf}
  System::Call '*(i 12,p r1,i 0) p .r2'
  System::Call 'kernel32::CreateDirectoryW(w "$InstallerPreflightRoot",p r2) i .r3'
  System::Free $2
  System::Call 'kernel32::LocalFree(p r1)'
  ${If} $3 == 0
    ${IfNot} ${Silent}
      MessageBox MB_ICONSTOP|MB_OK "The private installer preflight directory could not be allocated. Existing evidence has been retained."
    ${EndIf}
    SetErrorLevel 1
    Abort
  ${EndIf}
  SetOutPath "$InstallerPreflightRoot"
  File /oname=Install-SoAIRuntime.ps1 "${PAYLOAD_DIR}\installer-support\Install-SoAIRuntime.ps1"
  nsExec::ExecToLog '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$InstallerPreflightRoot\Install-SoAIRuntime.ps1" -PreflightOnly'
  Pop $0
  ${If} $0 != 0
    ${IfNot} ${Silent}
      MessageBox MB_ICONSTOP|MB_OK "Windows long-path support could not be enabled and verified. Setup has not changed the installation."
    ${EndIf}
    SetErrorLevel 1
    Abort
  ${EndIf}
  System::Call 'kernel32::SetEnvironmentVariableW(w "TEMP",w "$InstallerPreflightRoot") i .r0'
  System::Call 'kernel32::SetEnvironmentVariableW(w "TMP",w "$InstallerPreflightRoot") i .r1'
  ${If} $0 == 0
  ${OrIf} $1 == 0
    SetErrorLevel 1
    Abort
  ${EndIf}
  ${If} $InstallerIsRefreshWorker != 1
    Call RunRefreshedInstaller
  ${EndIf}
FunctionEnd

Function CreateInstallerJobObject
  Push $0
  Push $1
  Push $2
  System::Call 'kernel32::CreateJobObjectW(p 0,p 0) p .r0'
  ${If} $0 != 0
    System::Call '*(i 0,i 0,i 0,i 0,i 0x2000,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0) p .r1'
    System::Call 'kernel32::SetInformationJobObject(p r0,i 9,p r1,i 112) i .r2'
    System::Free $1
    ${If} $2 == 0
      System::Call 'kernel32::CloseHandle(p r0)'
      StrCpy $0 0
    ${EndIf}
  ${EndIf}
  Pop $2
  Pop $1
  Exch $0
FunctionEnd

Function CountInstallerJobProcesses
  Exch $0
  Push $1
  Push $2
  System::Call '*(l 0,l 0,l 0,l 0,i 0,i 0,i 0,i 0) p .r1'
  System::Call 'kernel32::QueryInformationJobObject(p r0,i 1,p r1,i 48,p 0) i .r2'
  ${If} $2 == 0
    StrCpy $0 -1
  ${Else}
    System::Call '*$1(l,l,l,l,i,i,i .r0,i)'
  ${EndIf}
  System::Free $1
  Pop $2
  Pop $1
  Exch $0
FunctionEnd

Function RunRefreshedInstaller
  System::Call 'kernel32::GetCurrentProcessId() i .r0'
  System::Call 'kernel32::SetEnvironmentVariableW(w "SOAI_INSTALL_REFRESH_PARENT_PID",w r0) i .r1'
  ${If} $1 == 0
    SetErrorLevel 1
    Abort
  ${EndIf}
  System::Call 'kernel32::SetEnvironmentVariableW(w "SOAI_INSTALL_REFRESH_RESULT_ROOT",w "$InstallerPreflightRoot") i .r1'
  ${If} $1 == 0
    SetErrorLevel 1
    Abort
  ${EndIf}
  Call CreateInstallerJobObject
  Pop $7
  ${If} $7 == 0
    SetErrorLevel 1
    Abort
  ${EndIf}
  System::Call 'kernel32::GetCommandLineW() p .r0'
  System::Call 'kernel32::lstrlenW(p r0) i .r1'
  IntOp $1 $1 + 1
  IntOp $1 $1 * 2
  System::Alloc $1
  Pop $2
  System::Call 'kernel32::lstrcpyW(p r2,p r0)'
  System::Call '*(i 68,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0,i 0) p .r3'
  System::Call '*(p 0,p 0,i 0,i 0) p .r4'
  System::Call 'kernel32::CreateProcessW(w "$EXEPATH",p r2,p 0,p 0,i 0,i 4,p 0,w "$EXEDIR",p r3,p r4) i .r5'
  System::Free $2
  System::Free $3
  System::Call 'kernel32::SetEnvironmentVariableW(w "SOAI_INSTALL_REFRESH_PARENT_PID",p 0)'
  ${If} $5 == 0
    System::Free $4
    System::Call 'kernel32::CloseHandle(p r7)'
    SetErrorLevel 1
    Abort
  ${EndIf}
  System::Call '*$4(p .r2,p .r3,i,i)'
  System::Free $4
  System::Call 'kernel32::AssignProcessToJobObject(p r7,p r2) i .r5'
  ${If} $5 == 0
    System::Call 'kernel32::TerminateProcess(p r2,i 1)'
    System::Call 'kernel32::WaitForSingleObject(p r2,i -1)'
    System::Call 'kernel32::CloseHandle(p r3)'
    System::Call 'kernel32::CloseHandle(p r2)'
    System::Call 'kernel32::CloseHandle(p r7)'
    SetErrorLevel 1
    Abort
  ${EndIf}
  System::Call 'kernel32::ResumeThread(p r3) i .r5'
  System::Call 'kernel32::CloseHandle(p r3)'
  ${If} $5 == -1
    System::Call 'kernel32::TerminateJobObject(p r7,i 1)'
  ${EndIf}
  System::Call 'kernel32::WaitForSingleObject(p r2,i 18000000) i .r5'
  ${If} $5 != 0
    System::Call 'kernel32::TerminateJobObject(p r7,i 1)'
    System::Call 'kernel32::WaitForSingleObject(p r2,i -1)'
    StrCpy $5 1
  ${Else}
    System::Call 'kernel32::GetExitCodeProcess(p r2,*i .r5)'
  ${EndIf}
  StrCpy $R0 $5
  System::Call 'kernel32::TerminateJobObject(p r7,i 1) i .r6'
  StrCpy $R1 0
  join_refresh_children:
    Push $7
    Call CountInstallerJobProcesses
    Pop $6
    ${If} $6 < 0
      StrCpy $R0 1
      Goto refresh_join_failed
    ${EndIf}
    ${If} $6 != 0
      IntOp $R1 $R1 + 1
      ${If} $R1 >= 3000
        StrCpy $R0 1
        Goto refresh_join_failed
      ${EndIf}
      Sleep 10
      Goto join_refresh_children
    ${EndIf}
  refresh_join_failed:
  System::Call 'kernel32::CloseHandle(p r2)'
  System::Call 'kernel32::CloseHandle(p r7)'
  StrCpy $5 $R0
  SetOutPath "$WINDIR\Temp"
  IfFileExists "$InstallerPreflightRoot\launch-root.txt" 0 refresh_launch_done
    FileOpen $0 "$InstallerPreflightRoot\launch-root.txt" r
    FileRead $0 $1
    FileClose $0
    SetOutPath "$1"
    Exec '"$1\soai.exe"'
    SetOutPath "$WINDIR\Temp"
  refresh_launch_done:
  ${If} $5 == 0
  ${OrIf} ${FileExists} "$InstallerPreflightRoot\${SOAI_DISPOSABLE_DIAGNOSTICS_MARKER}"
    RMDir /r "$InstallerPreflightRoot"
  ${EndIf}
  SetErrorLevel $5
  Quit
FunctionEnd

!macro DefineInstallerFilesystemPath PREFIX
Function ${PREFIX}InstallerFilesystemPath
  Exch $0
  Push $1
  StrCpy $1 $0 4
  ${If} $1 != "\\?\"
    ${GetRoot} "$0" $1
    ${If} $0 == "$1"
      StrCpy $0 "$0\"
    ${EndIf}
    StrCpy $1 $0 2
    ${If} $1 == "\\"
      StrCpy $0 $0 "" 2
      StrCpy $0 "\\?\UNC\$0"
    ${Else}
      StrCpy $0 "\\?\$0"
    ${EndIf}
  ${EndIf}
  Pop $1
  Exch $0
FunctionEnd
!macroend
!insertmacro DefineInstallerFilesystemPath ""
!insertmacro DefineInstallerFilesystemPath "un."

!macro DefineRemoveInstallerDirectory PREFIX
Function ${PREFIX}RemoveInstallerDirectory
  Exch $0
  Push $1
  Push $0
  Call ${PREFIX}InstallerFilesystemPath
  Pop $1
  System::Call 'kernel32::RemoveDirectoryW(w r1) i .r1'
  ${If} $1 != 0
    DetailPrint "Remove folder: $0"
    StrCpy $1 1
  ${EndIf}
  StrCpy $0 $1
  Pop $1
  Exch $0
FunctionEnd
!macroend
!insertmacro DefineRemoveInstallerDirectory ""
!insertmacro DefineRemoveInstallerDirectory "un."

!define SOAI_FAILURE_REASON_FILE "failure-reason.txt"
!define SOAI_REASON_TEXT_LIMIT 160

Function RecordInstallFailure
  Exch $0
  ${If} $InstallFailed != 1
    StrCpy $InstallFailed 1
    StrCpy $InstallFailureMessage $0
  ${EndIf}
  DetailPrint "$0"
  Pop $0
  SetErrorLevel 1
  ${If} ${Silent}
    Abort
  ${EndIf}
FunctionEnd

Function FormatInstallerReason
  Exch $0
  Push $1
  Push $2
  StrLen $1 $0
  ${If} $1 > ${SOAI_REASON_TEXT_LIMIT}
    StrCpy $0 $0 ${SOAI_REASON_TEXT_LIMIT}
    StrCpy $1 ${SOAI_REASON_TEXT_LIMIT}
    limit_word:
      IntOp $1 $1 - 1
      ${If} $1 > 0
        StrCpy $2 $0 1 $1
        ${If} $2 != " "
          Goto limit_word
        ${EndIf}
        StrCpy $0 $0 $1
      ${EndIf}
    StrCpy $0 "$0..."
  ${EndIf}
  StrCpy $1 $0 1 -1
  ${If} $1 != "."
  ${AndIf} $1 != "!"
  ${AndIf} $1 != "?"
    StrCpy $0 "$0."
  ${EndIf}
  Pop $2
  Pop $1
  Exch $0
FunctionEnd

Function ReadInstallerReason
  Exch $0
  Push $1
  Push $2
  StrCpy $1 ""
  ClearErrors
  FileOpen $2 "$0" r
  ${IfNot} ${Errors}
    FileSeek $2 2 SET
    FileReadUTF16LE $2 $1
    FileClose $2
  ${EndIf}
  trim_reason:
    StrCpy $2 $1 1 -1
    ${If} $2 == "$\r"
    ${OrIf} $2 == "$\n"
    ${OrIf} $2 == " "
      StrCpy $1 $1 -1
      Goto trim_reason
    ${EndIf}
  StrCpy $0 $1
  Pop $2
  Pop $1
  Exch $0
FunctionEnd

Function ComposeInstallerScriptFailure
  Exch $0
  Exch
  Exch $1
  Push $2
  StrCpy $2 ""
  IfFileExists "$PLUGINSDIR\${SOAI_FAILURE_REASON_FILE}" 0 compose_failure
    Push "$PLUGINSDIR\${SOAI_FAILURE_REASON_FILE}"
    Call ReadInstallerReason
    Pop $2
    System::Call 'kernel32::DeleteFileW(w "$PLUGINSDIR\${SOAI_FAILURE_REASON_FILE}")'
  compose_failure:
  ${If} $2 != ""
    Push $2
    Call FormatInstallerReason
    Pop $2
    StrCpy $0 "$0: $2"
  ${Else}
    StrCpy $0 "$0."
  ${EndIf}
  ${If} $1 != ""
    StrCpy $0 "$0 $1"
  ${EndIf}
  Pop $2
  Pop $1
  Exch $0
FunctionEnd

!macro RecordInstallerFailure PREFIX MESSAGE
  !if "${PREFIX}" == "un."
    SetErrorLevel 1
    Abort
  !else
    Push "${MESSAGE}"
    Call RecordInstallFailure
  !endif
!macroend

!macro FailInstallerStep PREFIX MESSAGE
  !insertmacro RecordInstallerFailure "${PREFIX}" "${MESSAGE}"
  Return
!macroend

!macro FailInstallerScript PREFIX CONTEXT HINT
  !if "${PREFIX}" == "un."
    SetErrorLevel 1
    Abort
  !else
    Push "${HINT}"
    Push "${CONTEXT}"
    Call ComposeInstallerScriptFailure
    Call RecordInstallFailure
    Return
  !endif
!macroend

!macro DefineAdmitInstallerTarget PREFIX
Function ${PREFIX}AdmitInstallerTarget
  InitPluginsDir
  SetOutPath "$PLUGINSDIR"
  File /oname=Admit-SoAIInstall.ps1 "${PAYLOAD_DIR}\installer-support\Admit-SoAIInstall.ps1"
  File /oname=soai-control.exe "${PAYLOAD_DIR}\soai.exe"
  File /oname=soai.exe.config "${PAYLOAD_DIR}\soai.exe.config"
  nsExec::ExecToLog '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\Admit-SoAIInstall.ps1" -InstallRoot "$INSTDIR" -CandidateConfigPath "$PLUGINSDIR\soai.exe.config" -CandidateVersion "${PRODUCT_VERSION}" -ClassificationPath "$PLUGINSDIR\target-classification.txt"'
  Pop $0
  ${If} $0 != 0
    !insertmacro FailInstallerScript "${PREFIX}" "Setup cannot install SoAI in $INSTDIR" ""
  ${EndIf}
  FileOpen $0 "$PLUGINSDIR\target-classification.txt" r
  FileRead $0 $InstallerTargetClassification
  FileClose $0
  FileOpen $0 "$PLUGINSDIR\target-classification.txt.target-root" r
  FileSeek $0 2 SET
  FileReadUTF16LE $0 $INSTDIR
  FileClose $0
  Push "$INSTDIR"
  Call ${PREFIX}InstallerFilesystemPath
  Pop $InstallerFilesystemRoot
  !if "${PREFIX}" == ""
    StrLen $0 "$InstallerFilesystemRoot"
    IntOp $0 $0 + ${PAYLOAD_MAX_RELATIVE_LENGTH}
    IntOp $0 $0 + 2
    ${If} $0 > ${NSIS_MAX_STRLEN}
      !insertmacro FailInstallerStep "" "The installation folder path is too long for the SoAI files. Choose a shorter folder, such as C:\SoAI."
    ${EndIf}
  !endif
  Push "$INSTDIR"
  Call ${PREFIX}RetainInstallerAncestors
  !if "${PREFIX}" == ""
    StrCmp $InstallFailed 1 admit_ancestors_retained
  !endif
  StrCpy $InstallerCreateDirectories 1
  Push "$INSTDIR\data\locks"
  Call ${PREFIX}RetainInstallerAncestors
  !if "${PREFIX}" == ""
    StrCmp $InstallFailed 1 admit_ancestors_retained
  !endif
  Push "$INSTDIR\data\state\locks"
  Call ${PREFIX}RetainInstallerAncestors
  !if "${PREFIX}" == ""
    admit_ancestors_retained:
  !endif
  StrCpy $InstallerCreateDirectories 0
  !if "${PREFIX}" == ""
    ${If} $InstallFailed == 1
      Return
    ${EndIf}
  !endif
  System::Call 'kernel32::CreateFileW(w "$InstallerFilesystemRoot\data\locks\soai.installation.transaction.lock",i 0xC0000000,i 3,p 0,i 4,i 0x80,p 0) p .r0'
  ${If} $0 == -1
    !insertmacro FailInstallerStep "${PREFIX}" "Setup could not open the SoAI installation lock in $INSTDIR."
  ${EndIf}
  StrCpy $InstallerTransactionHandle $0
  System::Call '*(i 0,i 0,i 0,i 0,i 0) p .r1'
  System::Call 'kernel32::LockFileEx(p $InstallerTransactionHandle,i 3,i 0,i 1,i 0,p r1) i .r2'
  System::Free $1
  ${If} $2 == 0
    !insertmacro FailInstallerStep "${PREFIX}" "Another SoAI setup or maintenance task is using $INSTDIR. Wait for it to finish, then run Setup again."
  ${EndIf}
  nsExec::ExecToLog '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\Admit-SoAIInstall.ps1" -InstallRoot "$INSTDIR" -CandidateConfigPath "$PLUGINSDIR\soai.exe.config" -CandidateVersion "${PRODUCT_VERSION}" -ClassificationPath "$PLUGINSDIR\target-classification.txt" -CandidateLauncherPath "$PLUGINSDIR\soai-control.exe" -Mode Transactions'
  Pop $0
  ${If} $0 != 0
    !insertmacro FailInstallerScript "${PREFIX}" "Setup could not verify unfinished SoAI maintenance in $INSTDIR" ""
  ${EndIf}
  StrCpy $InstallerLockDirectory "$InstallerFilesystemRoot\data\state\locks\soai.install.lock.d"
  System::Call 'kernel32::CreateDirectoryW(w "$InstallerLockDirectory",p 0) i .r0'
  ${If} $0 == 0
    !insertmacro FailInstallerStep "${PREFIX}" "An existing SoAI install lock in $INSTDIR requires recovery. Its ownership evidence has been retained."
  ${EndIf}
  System::Call 'kernel32::CreateFileW(w "$InstallerLockDirectory",i 0x80,i 3,p 0,i 3,i 0x02200000,p 0) p .r0'
  ${If} $0 == -1
    !insertmacro FailInstallerStep "${PREFIX}" "Setup could not acquire the SoAI installation lock in $INSTDIR."
  ${EndIf}
  StrCpy $InstallerLockHandle $0
  System::Call '*(l 0,l 0,l 0,l 0) p .r0'
  System::Call 'advapi32::SystemFunction036(p r0,i 32) i .r1'
  ${If} $1 == 0
    System::Free $0
    !insertmacro FailInstallerStep "${PREFIX}" "Setup could not acquire the SoAI installation lock in $INSTDIR."
  ${EndIf}
  StrCpy $InstallerLockToken ""
  StrCpy $1 0
  generate_lock_token:
    IntOp $2 $0 + $1
    System::Call '*$2(&i1 .r3)'
    IntFmt $3 "%02x" $3
    StrCpy $InstallerLockToken "$InstallerLockToken$3"
    IntOp $1 $1 + 1
    ${If} $1 < 32
      Goto generate_lock_token
    ${EndIf}
  System::Free $0
  System::Call 'kernel32::GetCurrentProcessId() i .r1'
  FileOpen $0 "$InstallerLockDirectory\pid" w
  FileWrite $0 "$1$\n"
  FileClose $0
  FileOpen $0 "$InstallerLockDirectory\token" w
  FileWrite $0 "$InstallerLockToken$\n"
  FileClose $0
  FileOpen $0 "$PLUGINSDIR\target-classification.txt.owner-start-ms" r
  FileRead $0 $2
  FileClose $0
  FileOpen $0 "$InstallerLockDirectory\owner-start-ms" w
  FileWrite $0 "$2"
  FileClose $0
  System::Call 'kernel32::SetEnvironmentVariableW(w "SOAI_INSTALL_LOCK_HELD_PATH",w "$INSTDIR\data\state\locks\soai.install.lock.d") i .r0'
  System::Call 'kernel32::SetEnvironmentVariableW(w "SOAI_INSTALL_LOCK_HELD_TOKEN",w "$InstallerLockToken") i .r1'
  System::Call 'kernel32::SetEnvironmentVariableW(w "SOAI_INSTALL_LOCK_OWNER_START_MS",w r2) i .r3'
  ${If} $0 == 0
  ${OrIf} $1 == 0
  ${OrIf} $3 == 0
    !insertmacro FailInstallerStep "${PREFIX}" "Setup could not acquire the SoAI installation lock in $INSTDIR."
  ${EndIf}
FunctionEnd
!macroend
!insertmacro DefineAdmitInstallerTarget ""
!insertmacro DefineAdmitInstallerTarget "un."

!macro DefineReleaseInstallerTarget PREFIX
Function ${PREFIX}ReleaseInstallerTarget
  ${If} $InstallerLockToken != ""
    FileOpen $0 "$InstallerLockDirectory\token" r
    FileRead $0 $1
    FileClose $0
    System::Call 'kernel32::GetCurrentProcessId() i .r2'
    FileOpen $0 "$InstallerLockDirectory\pid" r
    FileRead $0 $3
    FileClose $0
    ${If} $1 == "$InstallerLockToken$\n"
    ${AndIf} $3 == "$2$\n"
      ${If} $InstallerLockHandle != ""
        System::Call 'kernel32::CloseHandle(p $InstallerLockHandle)'
        StrCpy $InstallerLockHandle ""
      ${EndIf}
      System::Call 'kernel32::DeleteFileW(w "$InstallerLockDirectory\token")'
      System::Call 'kernel32::DeleteFileW(w "$InstallerLockDirectory\owner-start-ms")'
      System::Call 'kernel32::DeleteFileW(w "$InstallerLockDirectory\pid")'
      System::Call 'kernel32::RemoveDirectoryW(w "$InstallerLockDirectory")'
    ${Else}
      SetErrorLevel 1
    ${EndIf}
    StrCpy $InstallerLockToken ""
  ${EndIf}
  ${If} $InstallerLockHandle != ""
    System::Call 'kernel32::CloseHandle(p $InstallerLockHandle)'
    StrCpy $InstallerLockHandle ""
  ${EndIf}
  ${If} $InstallerTransactionHandle != ""
    System::Call 'kernel32::CloseHandle(p $InstallerTransactionHandle)'
    StrCpy $InstallerTransactionHandle ""
  ${EndIf}
  System::Call 'kernel32::SetEnvironmentVariableW(w "SOAI_INSTALL_LOCK_HELD_PATH",p 0)'
  System::Call 'kernel32::SetEnvironmentVariableW(w "SOAI_INSTALL_LOCK_HELD_TOKEN",p 0)'
  System::Call 'kernel32::SetEnvironmentVariableW(w "SOAI_INSTALL_LOCK_OWNER_START_MS",p 0)'
  StrCpy $InstallerPayloadAncestorBoundary 0
  Call ${PREFIX}ReleaseRetainedInstallerDirectories
FunctionEnd
!macroend
!insertmacro DefineReleaseInstallerTarget ""
!insertmacro DefineReleaseInstallerTarget "un."

Function ReleaseInstallerPayloadDirectories
  ${If} $InstallerPayloadExtractionStarted == 1
    Call ReleaseRetainedInstallerDirectories
    StrCpy $InstallerPayloadExtractionStarted 0
  ${EndIf}
FunctionEnd

!macro DefineReleaseRetainedInstallerDirectories PREFIX
Function ${PREFIX}ReleaseRetainedInstallerDirectories
  release_ancestor:
    ${If} $InstallerAncestorHandles != ""
    ${AndIf} $InstallerAncestorHandles != 0
    ${AndIf} $InstallerAncestorHandles != $InstallerPayloadAncestorBoundary
      StrCpy $0 $InstallerAncestorHandles
      System::Call '*$0(p .r1,p .r2)'
      System::Call 'kernel32::CloseHandle(p r2) i .r3'
      ${If} $3 == 0
        SetErrorLevel 1
        !if "${PREFIX}" == "un."
          Abort
        !endif
      ${EndIf}
      System::Free $0
      StrCpy $InstallerAncestorHandles $1
      Goto release_ancestor
    ${EndIf}
FunctionEnd
!macroend
!insertmacro DefineReleaseRetainedInstallerDirectories ""
!insertmacro DefineReleaseRetainedInstallerDirectories "un."

!macro DefineRetainInstallerAncestors PREFIX
Function ${PREFIX}RetainInstallerAncestors
  Exch $2
  Push $0
  Push $1
  Push $3
  Push $4
  Push $5
  Push $6
  ${GetRoot} "$2" $1
  ${If} $2 != "$1"
  ${AndIf} $2 != "$1\"
    ${GetParent} "$2" $1
    ${If} $1 != ""
    ${AndIf} $1 != "$2"
      Push $1
      Call ${PREFIX}RetainInstallerAncestors
      !if "${PREFIX}" == ""
        StrCmp $InstallFailed 1 retain_done
      !endif
    ${EndIf}
  ${EndIf}
    Push $2
    Call ${PREFIX}InstallerFilesystemPath
    Pop $3
    System::Call 'kernel32::GetFileAttributesW(w r3) i .r0 ?e'
    Pop $1
    ${If} $0 == -1
    ${AndIf} $InstallerCreateDirectories == 1
      ${If} $1 != 2
      ${AndIf} $1 != 3
        Goto retain_failed
      ${EndIf}
      System::Call 'kernel32::CreateDirectoryW(w r3,p 0) i .r0'
      ${If} $0 == 0
        Goto retain_failed
      ${EndIf}
      ${If} $InstallerCreatedRoot == ""
        StrCpy $InstallerCreatedRoot $2
      ${EndIf}
      System::Call 'kernel32::GetFileAttributesW(w r3) i .r0 ?e'
      Pop $1
    ${EndIf}
    ${If} $0 != -1
      IntOp $1 $0 & 0x410
      ${If} $1 <> 0x10
        Goto retain_failed
      ${EndIf}
      System::Call 'kernel32::CreateFileW(w r3,i 0x80,i 3,p 0,i 3,i 0x02200000,p 0) p .r4'
      ${If} $4 == -1
        Goto retain_failed
      ${EndIf}
      System::Call '*(i 0,i 0) p .r5'
      System::Call 'kernel32::GetFileInformationByHandleEx(p r4,i 9,p r5,i 8) i .r6'
      System::Call '*$5(i .r0,i)'
      System::Free $5
      IntOp $0 $0 & 0x410
      ${If} $6 == 0
      ${OrIf} $0 <> 0x10
        System::Call 'kernel32::CloseHandle(p r4)'
        Goto retain_failed
      ${EndIf}
      System::Call '*(p $InstallerAncestorHandles,p r4) p .r5'
      ${If} $5 == 0
        System::Call 'kernel32::CloseHandle(p r4)'
        Goto retain_failed
      ${EndIf}
      StrCpy $InstallerAncestorHandles $5
    ${ElseIf} $1 != 2
    ${AndIf} $1 != 3
      Goto retain_failed
    ${EndIf}
    Goto retain_done
  retain_failed:
    StrLen $0 $2
    ${If} $0 == 2
      StrCpy $2 "$2\"
    ${EndIf}
    !insertmacro RecordInstallerFailure "${PREFIX}" "Setup could not prepare the installation folder $2."
  retain_done:
  Pop $6
  Pop $5
  Pop $4
  Pop $3
  Pop $1
  Pop $0
  Pop $2
FunctionEnd
!macroend
!insertmacro DefineRetainInstallerAncestors ""
!insertmacro DefineRetainInstallerAncestors "un."
