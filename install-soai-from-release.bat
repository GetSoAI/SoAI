@echo off
setlocal EnableExtensions
set "SOAI_SCRIPT_DIR=%~dp0"
set "SOAI_INSTALL_SCRIPT_HAS_COMMAND=0"

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
if "%SOAI_INSTALL_SCRIPT_HAS_COMMAND%"=="0" (
    "%SOAI_SCRIPT_DIR%soai.exe" install %*
    exit /b %ERRORLEVEL%
)
"%SOAI_SCRIPT_DIR%soai.exe" %*
exit /b %ERRORLEVEL%
