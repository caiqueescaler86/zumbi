@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ZUMBI] Criando ambiente...
    py -3.12 -m venv .venv 2>nul
    if errorlevel 1 python -m venv .venv
)

call ".venv\Scripts\activate.bat"

rem Nao usa o cache global do pip. Evita erros de permissao em AppData\Local\pip\cache.
set "PIP_NO_CACHE_DIR=1"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

echo [ZUMBI] Instalando/verificando dependencias...
python -m pip install --no-cache-dir -r requirements-product.txt
if errorlevel 1 (
    echo.
    echo [ZUMBI] Falha instalando dependencias.
    echo [ZUMBI] Tentando reparar pip e instalar novamente...
    python -m ensurepip --upgrade
    python -m pip install --no-cache-dir --upgrade pip
    python -m pip install --no-cache-dir -r requirements-product.txt
)

if errorlevel 1 (
    echo.
    echo [ZUMBI] Nao foi possivel instalar as dependencias.
    pause
    exit /b 1
)

echo [ZUMBI] Iniciando...
python product_app.py
if errorlevel 1 pause
