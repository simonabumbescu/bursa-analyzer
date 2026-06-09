@echo off
REM ============================================================
REM  Analizor Actiuni BVB - pornire aplicatie
REM  Dublu-click pe acest fisier ca sa pornesti aplicatia.
REM ============================================================

title Analizor BVB

REM Mergi in folderul unde se afla acest fisier .bat
cd /d "%~dp0"

echo ============================================
echo   Pornesc Analizorul de actiuni BVB...
echo   Se va deschide singur in browser.
echo   NU inchide aceasta fereastra cat folosesti aplicatia.
echo ============================================
echo.

REM Verifica daca Python exista
python --version >nul 2>&1
if errorlevel 1 (
    echo [EROARE] Python nu este instalat sau nu este in PATH.
    echo Instaleaza Python de pe https://www.python.org/downloads/
    echo si bifeaza "Add Python to PATH" la instalare.
    pause
    exit /b 1
)

REM Verifica daca streamlit este instalat; daca nu, instaleaza dependentele
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo Prima pornire: instalez dependentele necesare...
    python -m pip install -r requirements.txt
    echo.
)

REM Porneste aplicatia (se deschide automat in browser pe http://localhost:8501)
python -m streamlit run app.py

REM Daca aplicatia se opreste, lasa fereastra deschisa ca sa vezi eventuale erori
echo.
echo Aplicatia s-a oprit.
pause
