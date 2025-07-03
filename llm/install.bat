@echo off
echo ====================================
echo 图片 LLM API 环境安装脚本
echo ====================================
echo.

echo 正在安装 Python 依赖包...
pip install -r requirements.txt

echo.
echo ====================================
echo 安装完成！
echo ====================================
echo.

echo 使用说明:
echo 1. 设置 API 密钥环境变量:
echo    set OPENAI_API_KEY=sk-your-actual-api-key
echo.
echo 2. 运行示例程序:
echo    python simple_example.py
echo.

echo 或者直接编辑 simple_example.py 文件中的 API_KEY 变量

pause
