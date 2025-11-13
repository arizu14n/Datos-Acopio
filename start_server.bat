@echo off
REM Activa el entorno virtual
call .\venv\Scripts\activate.bat

REM Establece la variable de entorno para Flask
set FLASK_APP=app.py

REM Sincroniza la base de datos desde los archivos DBF
echo "Sincronizando la base de datos con los archivos .dbf..."
@REM python sync_db.py

REM Inicia el servidor de Flask en segundo plano
echo "Iniciando servidor de Flask..."
start "Flask Server" /B flask run --host=0.0.0.0

REM Espera un momento para que el servidor se inicie
timeout /t 5 /nobreak > nul

REM Abre la página en el navegador
echo "Abriendo la pagina web..."
start http://127.0.0.1:5000/

echo "El servidor se esta ejecutando en segundo plano."
echo "Cierre esta ventana para detener el servidor."

REM Mantiene la ventana abierta hasta que se cierre manualmente
pause > nul
