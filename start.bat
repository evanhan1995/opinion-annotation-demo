@echo off
chcp 65001 >nul
cd /d "D:\Claude code\舆情标注Wiki"

echo ========================================
echo   舆情智能标注系统
echo ========================================
echo.
echo   正在启动...
echo   浏览器将自动打开 http://localhost:8501
echo   关闭此窗口即可停止服务
echo.
echo ========================================

start http://localhost:8501
streamlit run app.py --server.port 8501 --server.headless true
