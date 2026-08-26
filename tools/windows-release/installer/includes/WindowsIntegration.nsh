; SoAI - Windows installer integration [tools/windows-release/installer/includes/WindowsIntegration.nsh]
; SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

Function CreateWindowsIntegration
  DetailPrint "Registering SoAI with Windows..."
  Push 96
  Call SetInstallerProgress

  WriteRegStr HKLM "${PRODUCT_REGKEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "${PRODUCT_REGKEY}" "Version" "${PRODUCT_VERSION}"

  Call InstallSoAITypeFonts

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  WriteRegStr HKLM "${PRODUCT_UNINSTALL_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKLM "${PRODUCT_UNINSTALL_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "${PRODUCT_UNINSTALL_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKLM "${PRODUCT_UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${PRODUCT_UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\soai.exe"
  WriteRegStr HKLM "${PRODUCT_UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKLM "${PRODUCT_UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKLM "${PRODUCT_UNINSTALL_KEY}" "EstimatedSize" ${ESTIMATED_SIZE_KB}
  WriteRegDWORD HKLM "${PRODUCT_UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${PRODUCT_UNINSTALL_KEY}" "NoRepair" 1

  DetailPrint "Creating Start Menu and Desktop shortcuts..."
  Push 98
  Call SetInstallerProgress
  CreateDirectory "$SMPROGRAMS\SoAI"
  CreateShortCut "$SMPROGRAMS\SoAI\SoAI.lnk" "$INSTDIR\soai.exe" "" "$INSTDIR\soai.exe" 0 SW_SHOWNORMAL "" "Start SoAI"
  CreateShortCut "$SMPROGRAMS\SoAI\Uninstall SoAI.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0 SW_SHOWNORMAL "" "Uninstall SoAI"
  CreateShortCut "$DESKTOP\SoAI.lnk" "$INSTDIR\soai.exe" "" "$INSTDIR\soai.exe" 0 SW_SHOWNORMAL "" "Start SoAI"

  Push 100
  Call SetInstallerProgress
FunctionEnd
Function InstallSoAITypeFonts
  DetailPrint "Installing SoAIType fonts..."
  CreateDirectory "$FONTS"
  System::Call 'gdi32::RemoveFontResourceExW(w "$FONTS\SoAIType-Variable.ttf", i 0, p 0) i .r0'
  System::Call 'gdi32::RemoveFontResourceExW(w "$FONTS\SoAIType-VariableItalic.ttf", i 0, p 0) i .r0'
  CopyFiles /SILENT "$INSTDIR\frontend\assets\fonts\soaitype\variable\SoAIType[opsz,wght].ttf" "$FONTS\SoAIType-Variable.ttf"
  CopyFiles /SILENT "$INSTDIR\frontend\assets\fonts\soaitype\variable\SoAIType-Italic[opsz,wght].ttf" "$FONTS\SoAIType-VariableItalic.ttf"
  WriteRegStr HKLM "Software\Microsoft\Windows NT\CurrentVersion\Fonts" "SoAIType Variable (TrueType)" "SoAIType-Variable.ttf"
  WriteRegStr HKLM "Software\Microsoft\Windows NT\CurrentVersion\Fonts" "SoAIType Variable Italic (TrueType)" "SoAIType-VariableItalic.ttf"
  System::Call 'gdi32::AddFontResourceExW(w "$FONTS\SoAIType-Variable.ttf", i 0, p 0) i .r0'
  System::Call 'gdi32::AddFontResourceExW(w "$FONTS\SoAIType-VariableItalic.ttf", i 0, p 0) i .r0'
  SendMessage ${HWND_BROADCAST} ${WM_FONTCHANGE} 0 0 /TIMEOUT=5000
FunctionEnd
Function un.RemoveSoAITypeFonts
  DetailPrint "Removing SoAIType fonts..."
  System::Call 'gdi32::RemoveFontResourceExW(w "$FONTS\SoAIType-Variable.ttf", i 0, p 0) i .r0'
  System::Call 'gdi32::RemoveFontResourceExW(w "$FONTS\SoAIType-VariableItalic.ttf", i 0, p 0) i .r0'
  DeleteRegValue HKLM "Software\Microsoft\Windows NT\CurrentVersion\Fonts" "SoAIType Variable (TrueType)"
  DeleteRegValue HKLM "Software\Microsoft\Windows NT\CurrentVersion\Fonts" "SoAIType Variable Italic (TrueType)"
  Delete "$FONTS\SoAIType-Variable.ttf"
  Delete "$FONTS\SoAIType-VariableItalic.ttf"
  SendMessage ${HWND_BROADCAST} ${WM_FONTCHANGE} 0 0 /TIMEOUT=5000
FunctionEnd
