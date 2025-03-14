@echo off
echo Setting up Fantasy PL MCP Server...

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set "python_version=%%i"
echo Found Python version %python_version%

REM Navigate to server directory
cd server || (
    echo Error: server directory not found
    exit /b 1
)

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Create cache directory
echo Setting up cache directory...
if not exist fpl_cache mkdir fpl_cache

REM Installation complete
echo.
echo ✅ Fantasy PL MCP Server installation complete!
echo.
echo To run the server:
echo   1. Activate the virtual environment:
echo      server\venv\Scripts\activate.bat
echo.
echo   2. Run the server:
echo      cd server
echo      python server.py
echo.
echo   3. For testing with MCP Inspector:
echo      npx @modelcontextprotocol/inspector python server.py
echo.
echo   4. For integration with Claude Desktop:
echo      mcp install server.py --name "Fantasy PL"
echo.

REM Keep window open
pause