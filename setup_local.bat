@echo off
REM Setup Local Mistral 7B Environment - Windows
REM Utilise l'environnement virtuel .venv existant
REM Version: 2026-05-07 (Derniere version Mistral)

echo.
echo ========================================
echo [SETUP LOCAL MISTRAL 7B - .venv]
echo ========================================
echo.

REM Verifier .venv existe
if not exist ".venv" (
    echo [ERROR] Dossier .venv n'existe pas
    echo Creer d'abord: python -m venv .venv
    pause
    exit /b 1
)

echo [OK] .venv detecte
echo.


REM Activer .venv
echo [*] Activation .venv...
call .venv\Scripts\activate.bat

if errorlevel 1 (
    echo [ERROR] Impossible activer .venv
    pause
    exit /b 1
)

echo [OK] .venv active
echo.

REM Verifier Python dans .venv
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python non trouve dans .venv
    pause
    exit /b 1
)

echo [OK] Python detecte
python --version
echo.

REM Mettre a jour pip dans .venv
echo [*] Mise a jour pip...
python -m pip install --upgrade pip

echo.
echo [*] Installation dependances...
pip install -r requirements-local.txt

if errorlevel 1 (
    echo [ERROR] Erreur installation dependances
    pause
    exit /b 1
)

echo.
echo [OK] Dependances installees
echo.

REM Verifier Ollama CLI
echo [*] Verification Ollama CLI...
ollama --version >nul 2>&1

if errorlevel 1 (
    echo [WARNING] Ollama CLI n'est pas installe
    echo Telecharger: https://ollama.ai/download
    echo Windows: Executer .exe installer
    echo.
) else (
    echo [OK] Ollama CLI detecte
    ollama --version
)

echo.
echo ========================================
echo [SETUP TERMINE - .venv PRET]
echo ========================================
echo.
echo Commandes suivantes:
echo   1. Ollama: ollama serve ^(dans nouveau terminal^)
echo   2. Mistral: ollama pull mistral ^(quand Ollama running^)
echo   3. Streamlit: streamlit run streamlit_app.py
echo.
echo .venv deja active - vous pouvez executer directement!
echo.
pause
