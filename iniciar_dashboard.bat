@echo off
chcp 65001 > nul
title AI Sentinel - Monitor de Gobernanza, Seguridad y Pensadores de IA

echo ===================================================================
echo     AI SENTINEL: Seguridad, Gobernanza & Pensadores de la IA
echo ===================================================================
echo.
echo [*] Verificando dependencias necesarias...
python -m pip install -q -r requirements.txt

echo [*] Abriendo el panel en tu navegador web predeterminado...
start http://localhost:8000

echo [*] Iniciando servidor local en http://localhost:8000
echo [*] Para detener el monitor, puedes cerrar esta ventana o presionar Ctrl+C.
echo.

python app.py
pause
