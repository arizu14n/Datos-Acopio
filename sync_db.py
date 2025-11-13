import psycopg2
from psycopg2 import sql
from dbfread import DBF
import datetime
import os

# --- CONFIGURACIÓN ---
# Ruta base donde se encuentran los archivos .dbf
DBF_PATH_PREFIX = 'C:\\acocta5'

# --- CONFIGURACIÓN DE LA BASE DE DATOS POSTGRESQL ---
DB_NAME = "acopio_db"
DB_USER = "user"
DB_PASS = "password"
DB_HOST = "localhost"
DB_PORT = "5432"

def get_db_connection():
    """Establece la conexión con la base de datos PostgreSQL."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

def clean_date(d):
    """Limpia y valida fechas. Devuelve None si la fecha es inválida."""
    if isinstance(d, (datetime.date, datetime.datetime)):
        return d
    return None

def clean_numeric(n):
    """Limpia y valida valores numéricos. Devuelve None si no es un número."""
    if n is None:
        return None
    try:
        # Intenta convertir a float para manejar decimales y luego a string para la BD
        return float(n)
    except (ValueError, TypeError):
        return None

def sync_dbfs_to_postgres():
    """
    Sincroniza todos los archivos DBF especificados a sus respectivas tablas en PostgreSQL.
    El script es robusto y reporta errores sin detenerse.
    """
    conn = get_db_connection()
    if not conn:
        return

    try:
        with conn.cursor() as cursor:
            print("Conexión a PostgreSQL exitosa. Listo para sincronizar.")

            # --- Definición de las tablas a sincronizar ---
            # Cada tupla contiene: (nombre_tabla, nombre_archivo_dbf, create_statement, insert_statement, columnas)
            tables_to_sync = [
                (
                    'acocarpo', 'acocarpo.dbf',
                    """CREATE TABLE IF NOT EXISTS acocarpo (
                        G_FECHA DATE, G_CONTRATO VARCHAR(255), G_CODI VARCHAR(255), G_COSE VARCHAR(255),
                        G_SALDO NUMERIC, G_CONFIRM VARCHAR(1), G_ROMAN VARCHAR(255), G_CTG VARCHAR(255), G_DESTINO VARCHAR(255)
                    );""",
                    "INSERT INTO acocarpo (G_FECHA, G_CONTRATO, G_CODI, G_COSE, G_SALDO, G_CONFIRM, G_ROMAN, G_CTG, G_DESTINO) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    ['G_FECHA', 'G_CONTRATO', 'G_CODI', 'G_COSE', 'G_SALDO', 'G_CONFIRM', 'G_ROMAN', 'G_CTG', 'G_DESTINO']
                ),
                (
                    'liqven', 'liqven.dbf',
                    """CREATE TABLE IF NOT EXISTS liqven (
                        FEC_C DATE, CONTRATO VARCHAR(255), PESO NUMERIC, NET_CTA NUMERIC, NOM_C VARCHAR(255), FAC_C VARCHAR(255),
                        FA1_C VARCHAR(255), BRU_C NUMERIC, IVA_C NUMERIC, PREOPE NUMERIC, OTR_GAS NUMERIC, IVA_GAS NUMERIC,
                        GAS_COM NUMERIC, IVA_COM NUMERIC, GAS_VAR NUMERIC, IVA_VAR NUMERIC
                    );""",
                    "INSERT INTO liqven VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    ['FEC_C', 'CONTRATO', 'PESO', 'NET_CTA', 'NOM_C', 'FAC_C', 'FA1_C', 'BRU_C', 'IVA_C', 'PREOPE', 'OTR_GAS', 'IVA_GAS', 'GAS_COM', 'IVA_COM', 'GAS_VAR', 'IVA_VAR']
                ),
                (
                    'acogran', 'acogran.dbf',
                    "CREATE TABLE IF NOT EXISTS acogran (G_CODI VARCHAR(255) PRIMARY KEY, G_DESC VARCHAR(255));",
                    "INSERT INTO acogran (G_CODI, G_DESC) VALUES (%s, %s) ON CONFLICT (G_CODI) DO NOTHING",
                    ['G_CODI', 'G_DESC']
                ),
                (
                    'acograst', 'acograst.dbf',
                    "CREATE TABLE IF NOT EXISTS acograst (G_CODI VARCHAR(255), G_COSE VARCHAR(255), G_STOK NUMERIC, PRIMARY KEY (G_CODI, G_COSE));",
                    "INSERT INTO acograst (G_CODI, G_COSE, G_STOK) VALUES (%s, %s, %s) ON CONFLICT (G_CODI, G_COSE) DO NOTHING",
                    ['G_CODI', 'G_COSE', 'G_STOK']
                ),
                (
                    'contrat', 'contrat.dbf',
                    """CREATE TABLE IF NOT EXISTS contrat (
                        NROCONT_C VARCHAR(255) PRIMARY KEY, KILOPED_C NUMERIC, ENTREGA_C NUMERIC, LIQUIYA_C NUMERIC,
                        COSECHA_C VARCHAR(255), PRODUCT_C VARCHAR(255), APELCOM_C VARCHAR(255)
                    );""",
                    "INSERT INTO contrat VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (NROCONT_C) DO NOTHING",
                    ['NROCONT_C', 'KILOPED_C', 'ENTREGA_C', 'LIQUIYA_C', 'COSECHA_C', 'PRODUCT_C', 'APELCOM_C']
                ),
                (
                    'acohis', 'acohis.dbf',
                    """CREATE TABLE IF NOT EXISTS acohis (
                        G_FECHA DATE, G_CTG VARCHAR(255), G_CODI VARCHAR(255), G_COSE VARCHAR(255), O_PESO NUMERIC, O_NETO NUMERIC,
                        G_TARFLET NUMERIC, G_KILOMETR NUMERIC, G_CTAPLADE VARCHAR(255), G_CUILCHOF VARCHAR(255), G_CUITRAN VARCHAR(255), G_CTL VARCHAR(255)
                    );""",
                    "INSERT INTO acohis VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    ['G_FECHA', 'G_CTG', 'G_CODI', 'G_COSE', 'O_PESO', 'O_NETO', 'G_TARFLET', 'G_KILOMETR', 'G_CTAPLADE', 'G_CUILCHOF', 'G_CUITRAN', 'G_CTL']
                ),
                (
                    'sysmae', 'sysmae.dbf',
                    "CREATE TABLE IF NOT EXISTS sysmae (CLI_C VARCHAR(255) PRIMARY KEY, S_APELLI VARCHAR(255), S_LOCALI VARCHAR(255));",
                    "INSERT INTO sysmae (CLI_C, S_APELLI, S_LOCALI) VALUES (%s, %s, %s) ON CONFLICT (CLI_C) DO NOTHING",
                    ['CLI_C', 'S_APELLI', 'S_LOCALI']
                ),
                (
                    'choferes', 'choferes.dbf',
                    "CREATE TABLE IF NOT EXISTS choferes (C_DOCUMENT VARCHAR(255) PRIMARY KEY, C_NOMBRE VARCHAR(255));",
                    "INSERT INTO choferes (C_DOCUMENT, C_NOMBRE) VALUES (%s, %s) ON CONFLICT (C_DOCUMENT) DO NOTHING",
                    ['C_DOCUMENT', 'C_NOMBRE']
                ),
                (
                    'ccbcta', 'ccbcta.dbf',
                    """CREATE TABLE IF NOT EXISTS ccbcta (
                        VTO_F DATE, TIP_F VARCHAR(255), IMP_F NUMERIC, CLI_F VARCHAR(255),
                        FA1_F VARCHAR(255), FAC_F VARCHAR(255), CTA_P VARCHAR(255)
                    );""",
                    "INSERT INTO ccbcta VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    ['VTO_F', 'TIP_F', 'IMP_F', 'CLI_F', 'FA1_F', 'FAC_F', 'CTA_P']
                )
            ]

            # --- Proceso de Sincronización ---
            for table_name, dbf_filename, create_sql, insert_sql, columns in tables_to_sync:
                print(f"\n--- Procesando tabla: {table_name} ---")
                try:
                    # 1. Crear tabla si no existe
                    cursor.execute(create_sql)
                    print(f"Tabla '{table_name}' creada o ya existente.")

                    # 2. Truncar la tabla para empezar de cero
                    cursor.execute(f"TRUNCATE TABLE {table_name};")
                    print(f"Tabla '{table_name}' truncada.")

                    # 3. Leer el archivo DBF
                    dbf_path = os.path.join(DBF_PATH_PREFIX, dbf_filename)
                    dbf = DBF(dbf_path, encoding='iso-8859-1')
                    record_count = 0
                    error_count = 0

                    # 4. Insertar registros uno por uno
                    for rec in dbf:
                        record_count += 1
                        try:
                            # Limpiar y preparar datos
                            values = []
                            for col in columns:
                                val = rec.get(col)
                                # Lógica de limpieza mejorada y más explícita
                                col_upper = col.upper()
                                if 'FECHA' in col_upper or 'FEC_' in col_upper or 'VTO_' in col_upper:
                                    values.append(clean_date(val))
                                elif col_upper in ['G_SALDO', 'PESO', 'NET_CTA', 'BRU_C', 'IVA_C', 'PREOPE', 'OTR_GAS', 
                                                 'IVA_GAS', 'GAS_COM', 'IVA_COM', 'GAS_VAR', 'IVA_VAR', 'G_STOK', 
                                                 'KILOPED_C', 'ENTREGA_C', 'LIQUIYA_C', 'O_PESO', 'O_NETO', 
                                                 'G_TARFLET', 'G_KILOMETR', 'IMP_F']:
                                    values.append(clean_numeric(val))
                                else:
                                    values.append(val)
                            
                            cursor.execute(insert_sql, tuple(values))

                        except Exception as e:
                            error_count += 1
                            print(f"  [Error Fila #{record_count}] No se pudo insertar el registro en '{table_name}'. Causa: {e}")
                            print(f"  [Error Fila #{record_count}] Datos problemáticos: {dict(rec)}")
                    
                    print(f"Sincronización de '{table_name}' finalizada. Total de registros: {record_count}. Errores: {error_count}.")

                except FileNotFoundError:
                    print(f"  [Error Fatal] Archivo no encontrado: {dbf_path}. Saltando tabla '{table_name}'.")
                except Exception as e:
                    print(f"  [Error Fatal] Ocurrió un error inesperado procesando la tabla '{table_name}'. Causa: {e}")
            
            # Crear tablas base que no se sincronizan desde DBF
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS fletes (
                id SERIAL PRIMARY KEY, g_fecha DATE, g_ctg VARCHAR(255) UNIQUE, g_codi VARCHAR(255), g_cose VARCHAR(255),
                o_peso NUMERIC, o_neto NUMERIC, g_tarflet NUMERIC, g_kilomet INTEGER, g_ctaplade VARCHAR(255),
                g_cuilchof VARCHAR(255), importe NUMERIC, fuente VARCHAR(50)
            );""")
            print("\nTabla 'fletes' creada o ya existente.")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cupos_solicitados (
                id SERIAL PRIMARY KEY, contrato VARCHAR(255), grano VARCHAR(255), cosecha VARCHAR(255), cantidad INTEGER,
                fecha_solicitud DATE, nombre_persona VARCHAR(255), flete_id INTEGER REFERENCES fletes(id), codigo_cupo VARCHAR(255)
            );""")
            print("Tabla 'cupos_solicitados' creada o ya existente.")

        conn.commit()
        print("\n¡Sincronización completada! Todos los cambios han sido guardados en la base de datos.")

    except Exception as e:
        print(f"\nOcurrió un error crítico durante la transacción: {e}")
        if conn:
            conn.rollback()
            print("Se revirtieron todos los cambios de la transacción actual.")
    finally:
        if conn:
            conn.close()
            print("Conexión a la base de datos cerrada.")

if __name__ == '__main__':
    sync_dbfs_to_postgres()
