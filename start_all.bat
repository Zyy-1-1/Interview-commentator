@echo off
chcp 65001 >nul
title 面评家 · 一键启动
cd /d "%~dp0"

rem ---------- 定位 Python(优先项目 venv,其次 Conda 环境) ----------
set "ENV_PYTHON="
if exist "%~dp0backend\.venv\Scripts\python.exe" set "ENV_PYTHON=%~dp0backend\.venv\Scripts\python.exe"
if not defined ENV_PYTHON if exist "C:\miniconda\envs\interview-commentator\python.exe" set "ENV_PYTHON=C:\miniconda\envs\interview-commentator\python.exe"
if not defined ENV_PYTHON if exist "%USERPROFILE%\miniconda3\envs\interview-commentator\python.exe" set "ENV_PYTHON=%USERPROFILE%\miniconda3\envs\interview-commentator\python.exe"
if not defined ENV_PYTHON if exist "%USERPROFILE%\anaconda3\envs\interview-commentator\python.exe" set "ENV_PYTHON=%USERPROFILE%\anaconda3\envs\interview-commentator\python.exe"
if not defined ENV_PYTHON (
    echo [错误] 未找到可用的 Python 环境: 需要 backend\.venv 或 Conda 环境 interview-commentator。
    echo 请先按 README 创建环境并安装依赖。
    pause
    exit /b 1
)

echo ============================================
echo   面评家 · AI 模拟面试官  — 一键启动
echo   后端 :8000   前端 :5173
echo ============================================

rem ---------- 重置演示数据(make_demo.py,需在启动后端前执行) ----------
set "RESET_DEMO=Y"
set /p "RESET_DEMO=重置演示数据(清空重建 23 岗位含18官方精选+20 简历+面试记录+6 交流区热帖)?输入 N 跳过,直接回车=重置: "
if /i "%RESET_DEMO%"=="N" (
    echo [跳过] 演示数据重置
) else (
    echo [重置] 生成演示数据...
    "%ENV_PYTHON%" "%~dp0scripts\make_demo.py"
    if errorlevel 1 (
        echo [错误] make_demo.py 执行失败,请检查 Python 依赖与 backend\interview.db。
        pause
        exit /b 1
    )
    echo [完成] 演示数据已就绪
)

rem ---------- 后端 FastAPI ----------
netstat -ano | findstr ":8000 .*LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [跳过] 后端已在运行(8000)
) else (
    echo [启动] 后端 FastAPI...
    pushd "%~dp0backend"
    start "面评家后端 :8000" cmd /k ""%ENV_PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
    popd
)

rem ---------- 前端 Vite ----------
netstat -ano | findstr ":5173 .*LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [跳过] 前端已在运行(5173)
) else (
    echo [启动] 前端 Vite...
    pushd "%~dp0frontend"
    start "面评家前端 :5173" cmd /k "npm.cmd run dev"
    popd
)

rem ---------- 打开浏览器 ----------
timeout /t 4 /nobreak >nul
echo 打开 http://localhost:5173 (岗位大厅) ...
start "" http://localhost:5173/
echo 完成。两个服务各自开了一个终端窗口,关掉窗口即停止服务。
