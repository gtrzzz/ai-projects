@echo off
rem Procesa todo lo nuevo de "entrada" y lo deja en "salida":
rem   - partidas largas: busca los mejores momentos y crea un clip por cada uno (+ informe.html)
rem   - clips cortos (boton Crear de la PS5): los convierte enteros
rem Opciones extra, p. ej.:  procesar.bat --tipo truco --max-clips 5 --motor ffmpeg
cd /d "%~dp0"
set PYTHONUTF8=1
.venv\Scripts\python clipper.py lote %*
pause
