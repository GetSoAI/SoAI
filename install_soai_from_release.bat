@echo off
setlocal EnableExtensions DisableDelayedExpansion
for %%I in ("%~dp0.") do set "SOAI_SCRIPT_DIR=%%~sI"
start "" /wait "%SOAI_SCRIPT_DIR%\soai.exe" --soai-complete-install %*
set "SOAI_INSTALL_EXIT_CODE=%ERRORLEVEL%"
if not "%SOAI_INSTALL_EXIT_CODE%"=="0" echo ERROR: SoAI installation failed with exit code %SOAI_INSTALL_EXIT_CODE%. 1>&2
exit /b %SOAI_INSTALL_EXIT_CODE%
