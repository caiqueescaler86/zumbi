@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ZUMBI] Criando ambiente...
    py -3.12 -m venv .venv 2>nul
    if errorlevel 1 python -m venv .venv
)

call ".venv\Scripts\activate.bat"
python -m pip install --disable-pip-version-check -r requirements-product.txt
if errorlevel 1 (
    echo.
    echo [ZUMBI] Falha instalando dependencias.
    pause
    exit /b 1
)

python product_app.py
if errorlevel 1 pause
