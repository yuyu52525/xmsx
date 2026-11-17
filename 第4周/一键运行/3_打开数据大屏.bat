@echo off
REM ============================================================
REM  打开数据大屏
REM  （bat 只做找 Python + 转调，中文逻辑全在 py\run_w4.py）
REM ============================================================
setlocal
cd /d "%~dp0.."

set "PY=python"
if exist "C:\Users\y\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" (
  set "PY=C:\Users\y\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
)

"%PY%" "py\run_w4.py" screen
echo.
pause