@echo off
rem Abre el panel de Clipper en el navegador. Deja esta ventana abierta mientras lo usas.
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist .venv\Scripts\python.exe (
  echo Falta instalar: haz doble clic en instalar.bat primero.
  pause
  exit /b 1
)
rem Si ya estaba abierto, solo abre el navegador
curl.exe -s -o nul http://127.0.0.1:8765/api/estado && (
  start "" http://127.0.0.1:8765
  exit /b 0
)
rem Tras actualizar Clipper pueden faltar piezas nuevas: se instalan solas
.venv\Scripts\python -c "import fastapi, uvicorn, multipart" 2>nul || (
  echo === Instalando lo que falta de Python ===
  .venv\Scripts\python -m pip install -r requirements.txt || goto :fallo
)
pushd remotion
if not exist node_modules\.bin\vite.cmd (
  echo === Instalando lo que falta de Remotion ===
  call npm ci --no-fund --no-audit || (popd & goto :fallo)
)
rem Se recompila siempre: tarda unos segundos y asi nunca queda una version vieja
echo === Preparando el panel ===
call npm run panel:build || (popd & goto :fallo)
popd
.venv\Scripts\python -m panel.servidor
pause
exit /b 0

:fallo
echo.
echo Algo ha fallado al instalar. Copia el texto de arriba y pasamelo.
pause
exit /b 1
