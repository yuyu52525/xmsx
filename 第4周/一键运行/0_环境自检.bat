@echo off
REM ============================================================
REM  0_环境自检.bat  --  检查 Docker / 端口 / 服务 / 数据是否就绪
REM  逻辑全在 Python 里，bat 只负责找解释器和转调
REM  （bat 里写中文会被 cmd 代码页解析坏，第 3 周踩过）
REM ============================================================
setlocal
cd /d "%~dp0.."

set "PY=python"
if exist "C:\Users\y\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" (
  set "PY=C:\Users\y\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
)

"%PY%" "py\run_w4.py" check
echo.
pause