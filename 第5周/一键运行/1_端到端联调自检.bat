@echo off
REM ============================================================
REM  1_端到端联调自检.bat  --  run all 39 cross-layer consistency checks
REM  All logic lives in Python; the bat only locates the interpreter
REM  and forwards (Chinese text inside .bat breaks cmd code page).
REM ============================================================
setlocal
cd /d "%~dp0.."

set "PY=python"
if exist "C:\Users\y\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" (
  set "PY=C:\Users\y\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
)

"%PY%" "py\e2e_verify.py"
echo.
pause