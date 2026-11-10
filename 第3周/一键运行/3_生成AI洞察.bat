@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0..\py"
set "PYEXE="
if exist "%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" set "PYEXE=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if defined PYEXE goto :run
py -3.12 -c "import pandas" >nul 2>&1 && set "PYEXE=py -3.12"
if defined PYEXE goto :run
py -3.11 -c "import pandas" >nul 2>&1 && set "PYEXE=py -3.11"
if defined PYEXE goto :run
py -3.10 -c "import pandas" >nul 2>&1 && set "PYEXE=py -3.10"
if defined PYEXE goto :run
python -c "import pandas" >nul 2>&1 && set "PYEXE=python"
if defined PYEXE goto :run
echo.
echo [ERROR] No usable Python found.
echo Install Python 3.11 or 3.12, then run in the py folder:
echo   pip install pandas numpy scikit-learn matplotlib pyhive thrift openai langchain-core python-dotenv openpyxl
echo.
pause
exit /b 1
:run
%PYEXE% run.py insight
echo.
pause
