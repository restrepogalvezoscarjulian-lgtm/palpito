@echo off
title Palpito - motor de analisis financiero
chcp 65001 >nul
cd /d "%~dp0backend"

echo.
echo   Palpito se esta encendiendo. Esta ventana es el motor:
echo   NO LA CIERRE mientras use la aplicacion.
echo.
echo   Abriendo el navegador en http://localhost:8000 ...
echo.

rem Abre el navegador unos segundos despues, cuando el servidor ya responde.
start "" /b cmd /c "timeout /t 4 /nobreak >nul && start http://localhost:8000"

set PYTHONIOENCODING=utf-8
python -m uvicorn api:app --port 8000

echo.
echo   El motor se detuvo. Cierre esta ventana o pulse una tecla para salir.
pause >nul
