@echo off
REM ============================================================
REM  Analizor Actiuni BVB - INSTALARE pe calculator nou
REM  Ruleaza acest fisier O SINGURA DATA, la prima instalare.
REM  Dupa ce se termina, porneste aplicatia cu start.bat
REM ============================================================

title Instalare Analizor BVB
cd /d "%~dp0"

echo ===============================================
echo   INSTALARE Analizor Actiuni BVB
echo ===============================================
echo.

REM --- 1. Verifica Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo Python nu este instalat. Incerc sa-l instalez automat...
    echo.
    where winget >nul 2>&1
    if errorlevel 1 (
        echo [EROARE] Nu pot instala Python automat ^(winget lipseste^).
        echo.
        echo Te rog instaleaza Python manual:
        echo   1. Intra pe https://www.python.org/downloads/
        echo   2. Descarca si instaleaza Python 3.12
        echo   3. BIFEAZA "Add Python to PATH" la instalare
        echo   4. Ruleaza din nou acest install.bat
        echo.
        pause
        exit /b 1
    )
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    echo.
    echo Python s-a instalat. INCHIDE aceasta fereastra si ruleaza din nou install.bat
    echo ^(ca sa se actualizeze PATH-ul^).
    pause
    exit /b 0
)

echo Python gasit:
python --version
echo.

REM --- 2. Actualizeaza pip ---
echo Actualizez pip...
python -m pip install --upgrade pip
echo.

REM --- 3. Instaleaza dependentele ---
echo Instalez bibliotecile necesare ^(streamlit, yfinance, pandas, plotly, reportlab, matplotlib^)...
echo Poate dura cateva minute.
echo.
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [EROARE] Instalarea bibliotecilor a esuat. Verifica conexiunea la internet
    echo si ruleaza din nou install.bat
    pause
    exit /b 1
)

echo.
echo ===============================================
echo   INSTALARE FINALIZATA CU SUCCES!
echo ===============================================
echo.
echo Acum poti porni aplicatia cu dublu-click pe START.BAT
echo.
echo Vrei sa pornesti aplicatia acum? (apasa o tasta pentru DA, sau inchide fereastra)
pause >nul
call start.bat
