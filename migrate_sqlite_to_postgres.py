import sqlite3
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_batch
import datetime
import os

# --- CONFIGURACIÓN DE LA BASE DE DATOS POSTGRESQL ---
PG_DB_NAME = "acopio_db"
PG_DB_USER = "user"
PG_DB_PASS = "password"
PG_DB_HOST = "localhost"
PG_DB_PORT = "5432"

# --- CONFIGURACIÓN DE LA BASE DE DATOS SQLITE ---
SQLITE_DB_FILE = "fletes.db" # Nombre del archivo SQLite

def get_postgres_connection():
    """Establece la conexión con la base de datos PostgreSQL."""
    try:
        conn = psycopg2.connect(
            dbname=PG_DB_NAME,
            user=PG_DB_USER,
            password=PG_DB_PASS,
            host=PG_DB_HOST,
            port=PG_DB_PORT
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error al conectar a la base de datos PostgreSQL: {e}")
        return None

def get_sqlite_connection():
    """Establece la conexión con la base de datos SQLite."""
    try:
        conn = sqlite3.connect(SQLITE_DB_FILE)
        return conn
    except sqlite3.Error as e:
        print(f"Error al conectar a la base de datos SQLite '{SQLITE_DB_FILE}': {e}")
        return None

def get_sqlite_table_schema(sqlite_cursor, table_name):
    """Obtiene el esquema de una tabla SQLite."""
    sqlite_cursor.execute(f"PRAGMA table_info({table_name});")
    columns_info = sqlite_cursor.fetchall()
    schema = []
    for col in columns_info:
        col_name = col[1]
        col_type = col[2]
        schema.append({'name': col_name, 'type': col_type})
    return schema

def map_sqlite_type_to_postgres(sqlite_type):
    """Mapea tipos de datos de SQLite a PostgreSQL."""
    sqlite_type = sqlite_type.upper()
    if "INT" in sqlite_type:
        return "INTEGER"
    elif "TEXT" in sqlite_type:
        return "VARCHAR(255)" # O TEXT si se prefiere sin límite
    elif "REAL" in sqlite_type or "BLOB" in sqlite_type: # SQLite REAL es para floats
        return "NUMERIC"
    elif "DATE" in sqlite_type or "DATETIME" in sqlite_type:
        return "TIMESTAMP" # O DATE si solo se necesita la fecha
    else:
        return "VARCHAR(255)" # Tipo por defecto si no se reconoce

def migrate_table(sqlite_conn, pg_conn, table_name):
    """Migra una tabla específica de SQLite a PostgreSQL."""
    print(f"\n--- Migrando tabla: {table_name} ---")
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()

    try:
        # 1. Obtener esquema de SQLite
        sqlite_schema = get_sqlite_table_schema(sqlite_cursor, table_name)
        if not sqlite_schema:
            print(f"Advertencia: No se encontró el esquema para la tabla '{table_name}' en SQLite. Saltando.")
            return

        # 2. Construir y ejecutar CREATE TABLE en PostgreSQL
        columns_pg = []
        for col in sqlite_schema:
            pg_type = map_sqlite_type_to_postgres(col['type'])
            columns_pg.append(f"{col['name']} {pg_type}")
        
        create_table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns_pg)});
"
        pg_cursor.execute(create_table_sql)
        print(f"Tabla '{table_name}' creada o ya existente en PostgreSQL.")

        # Opcional: Truncar tabla en PostgreSQL antes de insertar (útil para re-ejecuciones)
        # pg_cursor.execute(f"TRUNCATE TABLE {table_name};")
        # print(f"Tabla '{table_name}' truncada en PostgreSQL.")

        # 3. Leer datos de SQLite
        sqlite_cursor.execute(f"SELECT * FROM {table_name};")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            print(f"No hay datos en la tabla '{table_name}' de SQLite para migrar.")
            return

        # 4. Insertar datos en PostgreSQL
        placeholders = ', '.join(['%s'] * len(sqlite_schema))
        insert_sql = f"INSERT INTO {table_name} VALUES ({placeholders});"
        
        # Usar execute_batch para inserciones eficientes
        execute_batch(pg_cursor, insert_sql, rows)
        pg_conn.commit()
        print(f"Migrados {len(rows)} registros de '{table_name}' a PostgreSQL.")

    except sqlite3.Error as e:
        print(f"Error de SQLite al procesar la tabla '{table_name}': {e}")
        pg_conn.rollback()
    except psycopg2.Error as e:
        print(f"Error de PostgreSQL al procesar la tabla '{table_name}': {e}")
        pg_conn.rollback()
    except Exception as e:
        print(f"Error inesperado al procesar la tabla '{table_name}': {e}")
        pg_conn.rollback()

def main():
    sqlite_conn = None
    pg_conn = None
    try:
        sqlite_conn = get_sqlite_connection()
        pg_conn = get_postgres_connection()

        if not sqlite_conn or not pg_conn:
            print("No se pudieron establecer todas las conexiones a la base de datos. Abortando.")
            return

        tables_to_migrate = ["cupos_solicitados", "fletes"]

        for table_name in tables_to_migrate:
            migrate_table(sqlite_conn, pg_conn, table_name)
        
        print("\n¡Migración de SQLite a PostgreSQL completada!")

    finally:
        if sqlite_conn:
            sqlite_conn.close()
        if pg_conn:
            pg_conn.close()
            print("Conexiones a bases de datos cerradas.")

if __name__ == '__main__':
    main()
