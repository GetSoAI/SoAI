@echo off
setlocal EnableExtensions
for %%I in ("%~dp0.") do set "SOAI_SCRIPT_DIR=%%~fI"
set "SOAI_INSTALL_SCRIPT_HAS_COMMAND=0"

if not exist "%SOAI_SCRIPT_DIR%\python\python.exe" (
    if not exist "%SOAI_SCRIPT_DIR%\installer-support\Install-SoAIRuntime.ps1" (
        echo ERROR: The Windows release is missing its runtime bootstrap script. 1>&2
        exit /b 1
    )
    powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%SOAI_SCRIPT_DIR%\installer-support\Install-SoAIRuntime.ps1" -InstallRoot "%SOAI_SCRIPT_DIR%" -BootstrapOnly
    if errorlevel 1 (
        echo ERROR: SoAI bootstrap runtime preparation failed. 1>&2
        exit /b 1
    )
)

call :scan_args %*
if "%SOAI_INSTALL_SCRIPT_HAS_COMMAND%"=="1" goto direct_command
echo ^>^>^> Installing SoAI to the selected Windows target...
start "" /wait "%SOAI_SCRIPT_DIR%\soai.exe" install %*
set "SOAI_INSTALL_EXIT_CODE=%ERRORLEVEL%"
if not "%SOAI_INSTALL_EXIT_CODE%"=="0" echo ERROR: SoAI target installation failed with exit code %SOAI_INSTALL_EXIT_CODE%. 1>&2
exit /b %SOAI_INSTALL_EXIT_CODE%

:direct_command
start "" /wait "%SOAI_SCRIPT_DIR%\soai.exe" %*
set "SOAI_INSTALL_EXIT_CODE=%ERRORLEVEL%"
if not "%SOAI_INSTALL_EXIT_CODE%"=="0" echo ERROR: SoAI command failed with exit code %SOAI_INSTALL_EXIT_CODE%. 1>&2
exit /b %SOAI_INSTALL_EXIT_CODE%

:scan_args
if "%~1"=="" goto args_scanned
if /I "%~1"=="install" set "SOAI_INSTALL_SCRIPT_HAS_COMMAND=1"
if /I "%~1"=="--install" set "SOAI_INSTALL_SCRIPT_HAS_COMMAND=1"
if /I "%~1"=="-install" set "SOAI_INSTALL_SCRIPT_HAS_COMMAND=1"
if /I "%~1"=="install-deps" set "SOAI_INSTALL_SCRIPT_HAS_COMMAND=1"
if /I "%~1"=="--install-deps" set "SOAI_INSTALL_SCRIPT_HAS_COMMAND=1"
if /I "%~1"=="-install-deps" set "SOAI_INSTALL_SCRIPT_HAS_COMMAND=1"
shift
goto scan_args

:args_scanned
exit /b 0
