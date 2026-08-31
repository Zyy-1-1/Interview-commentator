@echo off
chcp 65001 >nul
title 面评家 · 一键启动
cd /d "%~dp0"

echo ============================================
echo   面评家 · AI 模拟面试官  — 一键启动
echo   后端 :8000   前端 :5173
echo ============================================

rem ---------- 后端 FastAPI ----------
netstat -ano | findstr ":8000 .*LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [跳过] 后端已在运行(8000)
) else (
    echo [启动] 后端 FastAPI...
    start "面评家后端 :8000" cmd /k "cd /d %~dp0backend && py -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
)

rem ---------- 前端 Vite ----------
netstat -ano | findstr ":5173 .*LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [跳过] 前端已在运行(5173)
) else (
    echo [启动] 前端 Vite...
    start "面评家前端 :5173" cmd /k "cd /d %~dp0frontend && npm run dev"
)

rem ---------- 打开浏览器 ----------
timeout /t 4 /nobreak >nul
echo 打开 http://localhost:5173 (岗位大厅) ...
start "" http://localhost:5173/
echo 完成。两个服务各自开了一个终端窗口,关掉窗口即停止服务。
