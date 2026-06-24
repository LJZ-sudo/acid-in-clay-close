@echo off
chcp 65001 >nul
title FactoryLab 数字↔物理 发现闭环 · 演示
cd /d "%~dp0"
set PORT=5273

if not exist "dist\index.html" (
  echo [!] 未找到 dist 目录。
  echo     请先在有 Node 的电脑上执行:  npm install ^&^& npm run build
  echo     然后把整个 demo_frontend\dist 一起拷过来。
  pause
  exit /b 1
)

echo 正在启动本地演示服务器 http://127.0.0.1:%PORT%/ ...
echo 浏览器打开后按空格播放；自动播放地址带 ?autoplay=1
echo 录屏请在录屏软件里勾选「系统声音/扬声器」即可带配音。
echo 关闭本窗口即停止服务。
echo.

where python >nul 2>nul
if %errorlevel%==0 (
  start "" "http://127.0.0.1:%PORT%/?autoplay=1"
  python -m http.server %PORT% --directory dist
  exit /b 0
)

where npx >nul 2>nul
if %errorlevel%==0 (
  start "" "http://127.0.0.1:%PORT%/?autoplay=1"
  npx --yes serve -l %PORT% dist
  exit /b 0
)

echo [!] 这台电脑没有检测到 Python 或 Node，无法启动本地服务器。
echo     方案一: 安装 Python（勾选 Add to PATH）后重新双击本文件。
echo     方案二: 直接播放预先录制好的 mp4 成片（零依赖，最省事）。
pause
