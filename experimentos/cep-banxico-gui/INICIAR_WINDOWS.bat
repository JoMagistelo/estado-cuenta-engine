@echo off
cd /d "%~dp0"
py CEP_Banxico_GUI.py
if errorlevel 1 (
 echo No se pudo iniciar. Instala Python 3.10+ y marca Add Python to PATH.
 pause
)