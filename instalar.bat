@echo off
cd /d "%~dp0"
echo === Python (Whisper, detector) ===
if not exist .venv python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
echo === Remotion (edicion animada) ===
pushd remotion
call npm ci --no-fund --no-audit
call npx remotion browser ensure
popd
if not exist entrada mkdir entrada
if not exist salida mkdir salida
echo.
echo Listo. Mete tus clips o partidas en la carpeta "entrada" y ejecuta procesar.bat
pause
