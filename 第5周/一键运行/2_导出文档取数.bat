@echo off
REM ============================================================
REM  2_导出文档取数.bat  --  dump the KPI figures used by the five documents
REM  Output: ..\evidence\kpi_for_docs.txt
REM ============================================================
setlocal
cd /d "%~dp0.."

set "PY=python"
if exist "C:\Users\y\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" (
  set "PY=C:\Users\y\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
)

"%PY%" "py\fetch_kpi.py"
echo.
pause