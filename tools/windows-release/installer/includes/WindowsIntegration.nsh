; SoAI - Windows installer integration [tools/windows-release/installer/includes/WindowsIntegration.nsh]
; SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

!define SOAI_FONT_REGKEY "Software\Microsoft\Windows NT\CurrentVersion\Fonts"
!define SOAI_REGISTRATION_ABSENT "$\n"

!macro WriteRegistrationString KEY NAME VALUE PRIOR
  WriteRegStr HKLM "${KEY}" "${NAME}" "${VALUE}"
!macroend
!macro WriteRegistrationNumber KEY NAME VALUE PRIOR
  WriteRegDWORD HKLM "${KEY}" "${NAME}" ${VALUE}
!macroend
!macro SnapshotRegistrationString KEY NAME VALUE PRIOR
  ClearErrors
  ReadRegStr ${PRIOR} HKLM "${KEY}" "${NAME}"
  ${If} ${Errors}
    StrCpy ${PRIOR} "${SOAI_REGISTRATION_ABSENT}"
  ${EndIf}
!macroend
!macro SnapshotRegistrationNumber KEY NAME VALUE PRIOR
  ClearErrors
  ReadRegDWORD ${PRIOR} HKLM "${KEY}" "${NAME}"
  ${If} ${Errors}
    StrCpy ${PRIOR} "${SOAI_REGISTRATION_ABSENT}"
  ${EndIf}
!macroend
!macro RestoreRegistrationString KEY NAME VALUE PRIOR
  ${If} ${PRIOR} == "${SOAI_REGISTRATION_ABSENT}"
    DeleteRegValue HKLM "${KEY}" "${NAME}"
  ${Else}
    WriteRegStr HKLM "${KEY}" "${NAME}" "${PRIOR}"
  ${EndIf}
!macroend
!macro RestoreRegistrationNumber KEY NAME VALUE PRIOR
  ${If} ${PRIOR} == "${SOAI_REGISTRATION_ABSENT}"
    DeleteRegValue HKLM "${KEY}" "${NAME}"
  ${Else}
    WriteRegDWORD HKLM "${KEY}" "${NAME}" ${PRIOR}
  ${EndIf}
!macroend
!macro SoAIProductRegistration ACTION
  !insertmacro ${ACTION}String "${PRODUCT_REGKEY}" "InstallDir" "$INSTDIR" $RegistrationPriorInstallDir
  !insertmacro ${ACTION}String "${PRODUCT_REGKEY}" "Version" "${PRODUCT_VERSION}" $RegistrationPriorVersion
!macroend
!macro SoAIUninstallRegistration ACTION
  !insertmacro ${ACTION}String "${PRODUCT_UNINSTALL_KEY}" "DisplayName" "${PRODUCT_NAME}" $RegistrationPriorDisplayName
  !insertmacro ${ACTION}String "${PRODUCT_UNINSTALL_KEY}" "DisplayVersion" "${PRODUCT_VERSION}" $RegistrationPriorDisplayVersion
  !insertmacro ${ACTION}String "${PRODUCT_UNINSTALL_KEY}" "Publisher" "${PRODUCT_PUBLISHER}" $RegistrationPriorPublisher
  !insertmacro ${ACTION}String "${PRODUCT_UNINSTALL_KEY}" "InstallLocation" "$INSTDIR" $RegistrationPriorInstallLocation
  !insertmacro ${ACTION}String "${PRODUCT_UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\soai.exe" $RegistrationPriorDisplayIcon
  !insertmacro ${ACTION}String "${PRODUCT_UNINSTALL_KEY}" "UninstallString" "$\"$INSTDIR\Uninstall.exe$\"" $RegistrationPriorUninstallString
  !insertmacro ${ACTION}String "${PRODUCT_UNINSTALL_KEY}" "QuietUninstallString" "$\"$INSTDIR\Uninstall.exe$\" /S" $RegistrationPriorQuietUninstallString
  !insertmacro ${ACTION}Number "${PRODUCT_UNINSTALL_KEY}" "EstimatedSize" "${ESTIMATED_SIZE_KB}" $RegistrationPriorEstimatedSize
  !insertmacro ${ACTION}Number "${PRODUCT_UNINSTALL_KEY}" "NoModify" "1" $RegistrationPriorNoModify
  !insertmacro ${ACTION}Number "${PRODUCT_UNINSTALL_KEY}" "NoRepair" "1" $RegistrationPriorNoRepair
!macroend
!macro SoAIFontRegistration ACTION
  !insertmacro ${ACTION}String "${SOAI_FONT_REGKEY}" "SoAIType Variable (TrueType)" "SoAIType-Variable.ttf" $IntegrationPriorRegularFont
  !insertmacro ${ACTION}String "${SOAI_FONT_REGKEY}" "SoAIType Variable Italic (TrueType)" "SoAIType-VariableItalic.ttf" $IntegrationPriorItalicFont
!macroend
!macro CaptureRegistrationKey KEY EXISTED
  System::Call 'advapi32::RegOpenKeyExW(p 0x80000002,w "${KEY}",i 0,i 0x20119,*p .r1) i .r0'
  ${If} $0 == 0
    StrCpy ${EXISTED} 1
    System::Call 'advapi32::RegCloseKey(p r1)'
  ${Else}
    StrCpy ${EXISTED} 0
  ${EndIf}
!macroend

Function CreateWindowsIntegration
  DetailPrint "Registering SoAI with Windows..."
  Push 96
  Call SetInstallerProgress

  StrCpy $IntegrationStage 1
  Call InstallSoAITypeFonts
  ${If} $InstallFailed == 1
    Return
  ${EndIf}

  ClearErrors
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  ${If} ${Errors}
    !insertmacro FailInstallerStep "" "Setup could not create the SoAI uninstaller in $INSTDIR."
  ${EndIf}

  !insertmacro CaptureRegistrationKey "${PRODUCT_REGKEY}" $RegistrationProductKeyExisted
  !insertmacro CaptureRegistrationKey "${PRODUCT_UNINSTALL_KEY}" $RegistrationUninstallKeyExisted
  !insertmacro SoAIProductRegistration SnapshotRegistration
  !insertmacro SoAIUninstallRegistration SnapshotRegistration
  StrCpy $IntegrationStage 2
  ClearErrors
  !insertmacro SoAIProductRegistration WriteRegistration
  !insertmacro SoAIUninstallRegistration WriteRegistration
  ${If} ${Errors}
    !insertmacro FailInstallerStep "" "Setup could not register SoAI with Windows."
  ${EndIf}

  DetailPrint "Creating Start Menu and Desktop shortcuts..."
  Push 98
  Call SetInstallerProgress
  ClearErrors
  CreateDirectory "$SMPROGRAMS\SoAI"
  CreateShortCut "$SMPROGRAMS\SoAI\SoAI.lnk" "$INSTDIR\soai.exe" "" "$INSTDIR\soai.exe" 0 SW_SHOWNORMAL "" "Start SoAI"
  CreateShortCut "$SMPROGRAMS\SoAI\Uninstall SoAI.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0 SW_SHOWNORMAL "" "Uninstall SoAI"
  CreateShortCut "$DESKTOP\SoAI.lnk" "$INSTDIR\soai.exe" "" "$INSTDIR\soai.exe" 0 SW_SHOWNORMAL "" "Start SoAI"
  ${If} ${Errors}
    DetailPrint "Some SoAI shortcuts could not be created."
  ${EndIf}

  Push 100
  Call SetInstallerProgress
FunctionEnd
Function InstallSoAITypeFonts
  DetailPrint "Installing SoAIType fonts..."
  StrCpy $IntegrationRegularFontExisted 0
  StrCpy $IntegrationItalicFontExisted 0
  ${If} ${FileExists} "$FONTS\SoAIType-Variable.ttf"
    StrCpy $IntegrationRegularFontExisted 1
  ${EndIf}
  ${If} ${FileExists} "$FONTS\SoAIType-VariableItalic.ttf"
    StrCpy $IntegrationItalicFontExisted 1
  ${EndIf}
  !insertmacro SoAIFontRegistration SnapshotRegistration
  CreateDirectory "$FONTS"
  System::Call 'gdi32::RemoveFontResourceExW(w "$FONTS\SoAIType-Variable.ttf", i 0, p 0) i .r0'
  System::Call 'gdi32::RemoveFontResourceExW(w "$FONTS\SoAIType-VariableItalic.ttf", i 0, p 0) i .r0'
  System::Call 'kernel32::CopyFileW(w "$InstallerFilesystemRoot\frontend\assets\fonts\soaitype\variable\SoAIType[opsz,wght].ttf",w "$FONTS\SoAIType-Variable.ttf",i 0) i .r0'
  ${If} $0 == 0
    !insertmacro FailInstallerStep "" "Setup could not install the SoAIType fonts."
  ${EndIf}
  System::Call 'kernel32::CopyFileW(w "$InstallerFilesystemRoot\frontend\assets\fonts\soaitype\variable\SoAIType-Italic[opsz,wght].ttf",w "$FONTS\SoAIType-VariableItalic.ttf",i 0) i .r0'
  ${If} $0 == 0
    !insertmacro FailInstallerStep "" "Setup could not install the SoAIType fonts."
  ${EndIf}
  ClearErrors
  !insertmacro SoAIFontRegistration WriteRegistration
  ${If} ${Errors}
    !insertmacro FailInstallerStep "" "Setup could not register the SoAIType fonts."
  ${EndIf}
  System::Call 'gdi32::AddFontResourceExW(w "$FONTS\SoAIType-Variable.ttf", i 0, p 0) i .r0'
  System::Call 'gdi32::AddFontResourceExW(w "$FONTS\SoAIType-VariableItalic.ttf", i 0, p 0) i .r0'
  SendMessage ${HWND_BROADCAST} ${WM_FONTCHANGE} 0 0 /TIMEOUT=5000
FunctionEnd
Function RevertWindowsIntegration
  ${If} $IntegrationStage < 1
    Return
  ${EndIf}
  ${If} $IntegrationStage >= 2
    ${If} $RegistrationProductKeyExisted == 1
      !insertmacro SoAIProductRegistration RestoreRegistration
    ${Else}
      DeleteRegKey HKLM "${PRODUCT_REGKEY}"
    ${EndIf}
    ${If} $RegistrationUninstallKeyExisted == 1
      !insertmacro SoAIUninstallRegistration RestoreRegistration
    ${Else}
      DeleteRegKey HKLM "${PRODUCT_UNINSTALL_KEY}"
    ${EndIf}
  ${EndIf}
  System::Call 'gdi32::RemoveFontResourceExW(w "$FONTS\SoAIType-Variable.ttf", i 0, p 0) i .r0'
  System::Call 'gdi32::RemoveFontResourceExW(w "$FONTS\SoAIType-VariableItalic.ttf", i 0, p 0) i .r0'
  ${If} $IntegrationRegularFontExisted != 1
    Delete "$FONTS\SoAIType-Variable.ttf"
  ${EndIf}
  ${If} $IntegrationItalicFontExisted != 1
    Delete "$FONTS\SoAIType-VariableItalic.ttf"
  ${EndIf}
  !insertmacro SoAIFontRegistration RestoreRegistration
  ${If} ${FileExists} "$FONTS\SoAIType-Variable.ttf"
    System::Call 'gdi32::AddFontResourceExW(w "$FONTS\SoAIType-Variable.ttf", i 0, p 0) i .r0'
  ${EndIf}
  ${If} ${FileExists} "$FONTS\SoAIType-VariableItalic.ttf"
    System::Call 'gdi32::AddFontResourceExW(w "$FONTS\SoAIType-VariableItalic.ttf", i 0, p 0) i .r0'
  ${EndIf}
  SendMessage ${HWND_BROADCAST} ${WM_FONTCHANGE} 0 0 /TIMEOUT=5000
  StrCpy $IntegrationStage 0
FunctionEnd
Function un.RemoveSoAITypeFonts
  DetailPrint "Removing SoAIType fonts..."
  System::Call 'gdi32::RemoveFontResourceExW(w "$FONTS\SoAIType-Variable.ttf", i 0, p 0) i .r0'
  System::Call 'gdi32::RemoveFontResourceExW(w "$FONTS\SoAIType-VariableItalic.ttf", i 0, p 0) i .r0'
  DeleteRegValue HKLM "${SOAI_FONT_REGKEY}" "SoAIType Variable (TrueType)"
  DeleteRegValue HKLM "${SOAI_FONT_REGKEY}" "SoAIType Variable Italic (TrueType)"
  Delete "$FONTS\SoAIType-Variable.ttf"
  Delete "$FONTS\SoAIType-VariableItalic.ttf"
  SendMessage ${HWND_BROADCAST} ${WM_FONTCHANGE} 0 0 /TIMEOUT=5000
FunctionEnd
