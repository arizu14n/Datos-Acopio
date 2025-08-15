# lector_dbf.py

from dbfread import DBF

# --- Configura la ruta de tu archivo .dbf ---
# Asegúrate de que esta ruta sea la correcta en tu sistema
# Puedes usar una ruta de red si es necesario (ej. \\192.168.1.100\compartido\mi_tabla.dbf)
ruta_dbf = "C:\\acocta5\\acocarpo.dbf"

# --- Leyendo la tabla ---
try:
    # `DBF` lee el archivo y cada registro es un diccionario
    tabla_dbf = DBF(ruta_dbf, encoding='iso-8859-1') # El encoding es importante para caracteres especiales

    print(f"Se ha leído la tabla: {tabla_dbf.name}")
    print(f"Total de registros: {len(tabla_dbf)}")
    print("-" * 30)

    # --- Muestra los primeros 5 registros para verificar ---
    print("Primeros 5 registros:")
    for i, registro in enumerate(tabla_dbf):
        if i >= 5:
            break
        print(registro)

except FileNotFoundError:
    print(f"Error: No se encontró el archivo en la ruta: {ruta_dbf}")
except Exception as e:
    print(f"Ocurrió un error al leer el archivo: {e}")
