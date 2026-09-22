; SoAI - Windows installer runtime preparation [tools/windows-release/installer/includes/RuntimePreparation.nsh]
; SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

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
  CreateDirectory "$INSTDIR\installer-support\logs"
  GetTempFileName $RuntimeDiagnosticPath "$TEMP"
  Delete "$RuntimeDiagnosticPath"
  CreateDirectory "$RuntimeDiagnosticPath"
  StrCpy $RuntimeStatusPath "$INSTDIR\installer-support\logs\install-status.ini"
  StrCpy $RuntimeExitPath "$INSTDIR\installer-support\logs\install-exit-code.txt"
  StrCpy $RuntimeErrorPath "$INSTDIR\installer-support\logs\install-error.txt"
  StrCpy $RuntimeWrapperPath "$INSTDIR\installer-support\logs\run-install-runtime.ps1"
  Delete "$RuntimeStatusPath"
  Delete "$RuntimeExitPath"
  Delete "$RuntimeErrorPath"
  Delete "$RuntimeWrapperPath"

  FileOpen $0 "$RuntimeWrapperPath" w
  FileWrite $0 "$$ErrorActionPreference = 'Stop'$\r$\n"
  FileWrite $0 "$$exitCode = 0$\r$\n"
  FileWrite $0 "$$diagnosticRoot = $\"$RuntimeDiagnosticPath$\"$\r$\n"
  FileWrite $0 "try {$\r$\n"
  FileWrite $0 "  & $\"$INSTDIR\installer-support\Install-SoAIRuntime.ps1$\" -InstallRoot $\"$INSTDIR$\" -PythonVersion $\"${PYTHON_VERSION}$\" -PythonUrl $\"${PYTHON_URL}$\" -PythonSha256 $\"${PYTHON_SHA256}$\" -WebView2BootstrapperUrl $\"${WEBVIEW2_BOOTSTRAPPER_URL}$\" -StatusPath $\"$RuntimeStatusPath$\"$\r$\n"
  FileWrite $0 "} catch {$\r$\n"
  FileWrite $0 "  $$message = ($$_.Exception.Message -replace '[\r\n]+', ' ').Trim()$\r$\n"
  FileWrite $0 "  if ([string]::IsNullOrWhiteSpace($$message)) { $$message = 'SoAI runtime preparation failed.' }$\r$\n"
  FileWrite $0 "  Write-Host $$message$\r$\n"
  FileWrite $0 "  Set-Content -LiteralPath $\"$RuntimeErrorPath$\" -Value $$message -Encoding ASCII$\r$\n"
  FileWrite $0 "  try {$\r$\n"
  FileWrite $0 "    New-Item -ItemType Directory -Force -Path $$diagnosticRoot | Out-Null$\r$\n"
  FileWrite $0 "    $$logRoot = Join-Path $\"$INSTDIR$\" 'installer-support\logs'$\r$\n"
  FileWrite $0 "    if (Test-Path -LiteralPath $$logRoot -PathType Container) { Copy-Item -LiteralPath $$logRoot -Destination (Join-Path $$diagnosticRoot 'logs') -Recurse -Force }$\r$\n"
  FileWrite $0 "    Set-Content -LiteralPath (Join-Path $$diagnosticRoot 'install-error.txt') -Value $$message -Encoding UTF8$\r$\n"
  FileWrite $0 "  } catch {$\r$\n"
  FileWrite $0 "  }$\r$\n"
  FileWrite $0 "  $$exitCode = 1$\r$\n"
  FileWrite $0 "}$\r$\n"
  FileWrite $0 "Set-Content -LiteralPath $\"$RuntimeExitPath$\" -Value $$exitCode -Encoding ASCII$\r$\n"
  FileWrite $0 "exit $$exitCode$\r$\n"
  FileClose $0
FunctionEnd
Function RuntimePrepStart
  StrCpy $LastRuntimeStatusMessage ""
  StrCpy $RuntimePollTicks 0
  StrCpy $RuntimeNoStatusTicks 0
  StrCpy $RuntimeCurrentProgress 35
  StrCpy $RuntimePrepFailed 0
  StrCpy $RuntimePrepFinished 0
  Call CreateRuntimePrepWrapper
  ExecShell "open" "${SOAI_NATIVE_POWERSHELL}" '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -NonInteractive -File "$RuntimeWrapperPath"' SW_HIDE
FunctionEnd
Function ReadRuntimeErrorMessage
  StrCpy $1 "SoAI runtime preparation failed."
  IfFileExists "$RuntimeErrorPath" 0 done
    FileOpen $0 "$RuntimeErrorPath" r
    FileRead $0 $1
    FileClose $0
    ${If} $1 == ""
      StrCpy $1 "SoAI runtime preparation failed."
    ${EndIf}

  done:
FunctionEnd
Function RuntimePrepRunSilent
  DetailPrint "Preparing SoAI for first start..."
  Call CreateRuntimePrepWrapper
  nsExec::ExecToLog '"${SOAI_NATIVE_POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -NonInteractive -File "$RuntimeWrapperPath"'
  Pop $0
  ${If} $0 != 0
    Call ReadRuntimeErrorMessage
    DetailPrint "SoAI could not be prepared: $1"
    SetOutPath "$TEMP"
    ${If} $UpgradePrepared == 1
      Call RestoreExistingInstallRoot
    ${Else}
      Call CleanupFailedFreshInstall
    ${EndIf}
    SetErrorLevel 1
    Abort
  ${EndIf}
  RMDir /r "$RuntimeDiagnosticPath"

  Call CreateWindowsIntegration
FunctionEnd
Function RuntimePrepFinishFailed
  ${NSD_KillTimer} RuntimePrepTimer
  StrCpy $RuntimePrepFailed 1
  Call ReadRuntimeErrorMessage
  ${NSD_SetText} $RuntimePageStatusLabel "SoAI could not be prepared: $1"
  SetOutPath "$TEMP"
  ${If} $UpgradePrepared == 1
    ${NSD_SetText} $RuntimePageDetailLabel "Setup is restoring the previous SoAI application files. Please wait until this setup window closes before running the installer again."
    Call RestoreExistingInstallRoot
    ${If} $UpgradeRollbackCompleted == 1
      MessageBox MB_ICONSTOP|MB_OK "SoAI could not be prepared.$\r$\n$\r$\n$1$\r$\n$\r$\nThe previous SoAI application files were restored and user data was retained.$\r$\n$\r$\nDiagnostic bundle: $RuntimeDiagnosticPath"
    ${Else}
      MessageBox MB_ICONSTOP|MB_OK "SoAI could not be prepared.$\r$\n$\r$\n$1$\r$\n$\r$\nSetup could not fully restore the previous application files. Restart Windows before running the installer again. User data was not removed.$\r$\n$\r$\nDiagnostic bundle: $RuntimeDiagnosticPath"
    ${EndIf}
  ${Else}
    ${NSD_SetText} $RuntimePageDetailLabel "Setup is removing the incomplete installation. Please wait until this setup window closes before running the installer again."
    Call CleanupFailedFreshInstall
    ${If} $0 == 0
      MessageBox MB_ICONSTOP|MB_OK "SoAI could not be prepared.$\r$\n$\r$\n$1$\r$\n$\r$\nThe incomplete installation has been removed. If this setup window is still open, close it before running the installer again.$\r$\n$\r$\nDiagnostic bundle: $RuntimeDiagnosticPath"
    ${Else}
      MessageBox MB_ICONSTOP|MB_OK "SoAI could not be prepared.$\r$\n$\r$\n$1$\r$\n$\r$\nSetup could not fully remove the incomplete installation. Wait for this setup window to close, then restart Windows and run the installer again.$\r$\n$\r$\nDiagnostic bundle: $RuntimeDiagnosticPath"
    ${EndIf}
  ${EndIf}
  ${If} $UpgradeRollbackCompleted == 1
    Quit
  ${ElseIf} $InstallMutationStarted == 0
    Quit
  ${Else}
    Abort
  ${EndIf}
FunctionEnd
Function RuntimePrepFinishSucceeded
  ${NSD_KillTimer} RuntimePrepTimer
  StrCpy $RuntimePrepFinished 1
  ${NSD_SetText} $RuntimePageStatusLabel "Finalizing SoAI installation..."
  RMDir /r "$RuntimeDiagnosticPath"
  Push 96
  Call SetInstallerProgress
  Call CreateWindowsIntegration
  Push 100
  Call SetInstallerProgress
  ${NSD_SetText} $RuntimePageStatusLabel "SoAI is ready to start."
  ${NSD_SetText} $RuntimePageDetailLabel "Setup is completing."
  GetDlgItem $0 $HWNDPARENT 1
  EnableWindow $0 1
  SendMessage $HWNDPARENT ${WM_COMMAND} 1 0
FunctionEnd
Function RuntimePrepTimer
  IntOp $RuntimePollTicks $RuntimePollTicks + 1
  ${If} $RuntimePollTicks > 21600
    Call RuntimePrepFinishFailed
    Return
  ${EndIf}

  IfFileExists "$RuntimeStatusPath" 0 no_status
    StrCpy $RuntimeNoStatusTicks 0
    ReadINIStr $1 "$RuntimeStatusPath" "status" "progress"
    ReadINIStr $2 "$RuntimeStatusPath" "status" "message"
    ${If} $1 != ""
      StrCpy $RuntimeCurrentProgress "$1"
      Push $RuntimeCurrentProgress
      Call SetInstallerProgress
    ${EndIf}
    ${If} $2 != ""
    ${AndIf} $2 != $LastRuntimeStatusMessage
      ${NSD_SetText} $RuntimePageStatusLabel "$2"
      StrCpy $LastRuntimeStatusMessage "$2"
    ${EndIf}
    Goto check_exit

  no_status:
    IntOp $RuntimeNoStatusTicks $RuntimeNoStatusTicks + 1
    ${If} $RuntimeNoStatusTicks > 120
      Call RuntimePrepFinishFailed
      Return
    ${EndIf}

  check_exit:
    IfFileExists "$RuntimeExitPath" 0 done
    FileOpen $0 "$RuntimeExitPath" r
    FileRead $0 $1
    FileClose $0
    ${If} $1 != "0$\r$\n"
    ${AndIf} $1 != "0$\n"
    ${AndIf} $1 != "0"
      Call RuntimePrepFinishFailed
      Return
    ${EndIf}
    Call RuntimePrepFinishSucceeded

  done:
FunctionEnd
Function RuntimePrepPageCreate
  StrCpy $RuntimePageProgress ""
  GetDlgItem $0 $HWNDPARENT 1037
  ${NSD_SetText} $0 "Preparing SoAI"
  GetDlgItem $0 $HWNDPARENT 1038
  ${NSD_SetText} $0 "Please wait while SoAI is prepared for first start."

  nsDialogs::Create 1018
  Pop $RuntimePageDialog
  ${If} $RuntimePageDialog == error
    Abort
  ${EndIf}

  ${NSD_CreateLabel} 0u 0u 100% 18u "Preparing SoAI runtime..."
  Pop $RuntimePageStatusLabel
  ${NSD_CreateProgressBar} 0u 24u 100% 12u ""
  Pop $RuntimePageProgress
  SendMessage $RuntimePageProgress ${PBM_SETRANGE32} 0 100
  SendMessage $RuntimePageProgress ${PBM_SETPOS} 35 0
  ${NSD_CreateLabel} 0u 46u 100% 44u "This can take several minutes while SoAI downloads and prepares required components. Please do not close the installer."
  Pop $RuntimePageDetailLabel

  GetDlgItem $0 $HWNDPARENT 1
  EnableWindow $0 0
  GetDlgItem $0 $HWNDPARENT 3
  EnableWindow $0 0

  Call RuntimePrepStart
  ${NSD_CreateTimer} RuntimePrepTimer 1000
  nsDialogs::Show
FunctionEnd
Function RuntimePrepPageLeave
  ${If} $RuntimePrepFinished != 1
    Abort
  ${EndIf}
FunctionEnd
