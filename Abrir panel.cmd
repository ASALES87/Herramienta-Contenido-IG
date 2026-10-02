@echo off
rem Abre el panel de la Herramienta Contenido IG en el navegador. Cierra esta ventana para pararlo.
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
%PY% -c "import PIL, requests" >nul 2>nul || %PY% -m pip install -q -r requirements.txt
%PY% panel\servidor.py
pause
