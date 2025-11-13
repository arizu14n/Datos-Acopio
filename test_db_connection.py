
import psycopg2
import sys

try:
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        user="user",
        password="password",
        dbname="acopio_db",
        connect_timeout=5
    )
    print("Conexión a la base de datos PostgreSQL exitosa.")
    conn.close()
    sys.exit(0)
except psycopg2.OperationalError as e:
    print(f"Error: No se pudo conectar a la base de datos PostgreSQL.")
    print(f"Detalle: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Ocurrió un error inesperado: {e}")
    sys.exit(1)
