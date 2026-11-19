@echo off
rem Abre el panel de Clipper en el navegador. Deja esta ventana abierta mientras lo usas.
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist .venv\Scripts\python.exe (
  echo Falta instalar: haz doble clic en instalar.bat primero.
  pause
  exit /b 1
)
if not exist remotion\panel-dist\index.html (
  echo Compilando el panel por primera vez...
  pushd remotion
  call npm run panel:build
  popd
)
rem Si ya estaba abierto, solo abre el navegador
curl.exe -s -o nul http://127.0.0.1:8765/api/estado && (
  start "" http://127.0.0.1:8765
  exit /b 0
)
.venv\Scripts\python -m panel.servidor
pause
