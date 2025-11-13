@echo off
REM Activa el entorno virtual
call .\venv\Scripts\activate.bat

REM Establece la variable de entorno para Flask
set FLASK_APP=app.py

REM Sincroniza la base de datos desde los archivos DBF
echo "Sincronizando la base de datos con los archivos .dbf..."
python sync_db.py