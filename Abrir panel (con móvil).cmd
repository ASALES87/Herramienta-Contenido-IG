@echo off
rem Abre el panel y deja entrar al movil (misma wifi) en la app Enviar foto y la vista del cliente.
rem El panel interno sigue siendo solo de este ordenador.
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
%PY% -c "import PIL, requests" >nul 2>nul || %PY% -m pip install -q -r requirements.txt
%PY% panel\servidor.py --red
pause
