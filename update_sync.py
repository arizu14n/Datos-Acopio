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
        return float(n)
    except (ValueError, TypeError):
        return None

def update_dbfs_to_postgres():
    """
    Sincroniza archivos DBF a PostgreSQL usando una estrategia de "upsert" (actualizar o insertar).
    No borra las tablas.
    """
    conn = get_db_connection()
    if not conn:
        return

    try:
        with conn.cursor() as cursor:
            print("Conexión a PostgreSQL exitosa. Iniciando sincronización por actualización.")

            # Definición de las tablas a sincronizar con estrategia de UPSERT
            # (table_name, dbf_filename, columns, pk_columns)
            # Si pk_columns es None, se usará la estrategia de borrar e insertar por fecha.
            tables_to_sync = [
                ('acocarpo', 'acocarpo.dbf', ['G_FECHA', 'G_CONTRATO', 'G_CODI', 'G_COSE', 'G_SALDO', 'G_CONFIRM', 'G_ROMAN', 'G_CTG', 'G_DESTINO'], None),
                ('liqven', 'liqven.dbf', ['FEC_C', 'CONTRATO', 'PESO', 'NET_CTA', 'NOM_C', 'FAC_C', 'FA1_C', 'BRU_C', 'IVA_C', 'PREOPE', 'OTR_GAS', 'IVA_GAS', 'GAS_COM', 'IVA_COM', 'GAS_VAR', 'IVA_VAR'], None),
                ('acogran', 'acogran.dbf', ['G_CODI', 'G_DESC'], ['G_CODI']),
                ('acograst', 'acograst.dbf', ['G_CODI', 'G_COSE', 'G_STOK'], ['G_CODI', 'G_COSE']),
                ('contrat', 'contrat.dbf', ['NROCONT_C', 'KILOPED_C', 'ENTREGA_C', 'LIQUIYA_C', 'COSECHA_C', 'PRODUCT_C', 'APELCOM_C', 'FECONT_C'], ['NROCONT_C']),
                ('acohis', 'acohis.dbf', ['G_FECHA', 'G_CTG', 'G_CODI', 'G_COSE', 'O_PESO', 'O_NETO', 'G_TARFLET', 'G_KILOMETR', 'G_CTAPLADE', 'G_CUILCHOF', 'G_CUITRAN', 'G_CTL', 'CLI_C', 'G_LOCALI'], None),
                ('sysmae', 'sysmae.dbf', ['CLI_C', 'S_APELLI', 'S_LOCALI', 'S_ZONACU'], ['CLI_C']),
                ('choferes', 'choferes.dbf', ['C_DOCUMENT', 'C_NOMBRE'], ['C_DOCUMENT']),
                ('ccbcta', 'ccbcta.dbf', ['VTO_F', 'TIP_F', 'IMP_F', 'CLI_F', 'FA1_F', 'FAC_F', 'CTA_P'], None)
            ]

            for table_name, dbf_filename, columns, pk_columns in tables_to_sync:
                print(f"\n--- Procesando tabla: {table_name} ---")
                try:
                    dbf_path = os.path.join(DBF_PATH_PREFIX, dbf_filename)
                    dbf = DBF(dbf_path, encoding='iso-8859-1')
                    
                    record_count = 0
                    error_count = 0
                    skipped_count = 0
                    upserted_count = 0

                    date_field_map = {
                        'acohis': 'G_FECHA', 'liqven': 'FEC_C', 'ccbcta': 'VTO_F',
                        'acocarpo': 'G_FECHA', 'contrat': 'FECONT_C'
                    }
                    date_field = date_field_map.get(table_name)

                    # Estrategia "Delete-then-Insert" para tablas sin PK definida
                    if pk_columns is None and date_field:
                        print(f"  Estrategia: Borrar e Insertar para registros desde 2023.")
                        cursor.execute(sql.SQL("DELETE FROM {} WHERE {} >= %s").format(
                            sql.Identifier(table_name),
                            sql.Identifier(date_field)
                        ), [datetime.date(2023, 1, 1)])
                        print(f"  Registros desde 2023 eliminados de '{table_name}'.")

                    # Construcción de la sentencia de UPSERT para tablas con PK
                    insert_sql = None
                    if pk_columns:
                        update_cols = [col for col in columns if col not in pk_columns]
                        if not update_cols: # Si no hay columnas que actualizar, solo se inserta si no existe
                            insert_sql = sql.SQL("INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT ({pks}) DO NOTHING").format(
                                table=sql.Identifier(table_name),
                                cols=sql.SQL(', ').join(map(sql.Identifier, columns)),
                                placeholders=sql.SQL(', ').join(sql.Placeholder() * len(columns)),
                                pks=sql.SQL(', ').join(map(sql.Identifier, pk_columns))
                            )
                        else:
                            assign_placeholders = sql.SQL(', ').join(
                                sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col)) for col in update_cols
                            )
                            insert_sql = sql.SQL("INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT ({pks}) DO UPDATE SET {assigns}").format(
                                table=sql.Identifier(table_name),
                                cols=sql.SQL(', ').join(map(sql.Identifier, columns)),
                                placeholders=sql.SQL(', ').join(sql.Placeholder() * len(columns)),
                                pks=sql.SQL(', ').join(map(sql.Identifier, pk_columns)),
                                assigns=assign_placeholders
                            )
                    else: # SQL para "Delete-then-Insert"
                        insert_sql = sql.SQL("INSERT INTO {table} ({cols}) VALUES ({placeholders})").format(
                            table=sql.Identifier(table_name),
                            cols=sql.SQL(', ').join(map(sql.Identifier, columns)),
                            placeholders=sql.SQL(', ').join(sql.Placeholder() * len(columns))
                        )
                    
                    for rec in dbf:
                        record_count += 1
                        
                        if date_field:
                            record_date = rec.get(date_field)
                            if record_date and isinstance(record_date, datetime.date) and record_date.year < 2023:
                                skipped_count += 1
                                continue
                        
                        try:
                            values = []
                            for col in columns:
                                val = rec.get(col)
                                col_upper = col.upper()
                                if 'FECHA' in col_upper or 'FEC_' in col_upper or 'VTO_' in col_upper:
                                    values.append(clean_date(val))
                                elif isinstance(val, (int, float, Decimal)):
                                     values.append(clean_numeric(val))
                                else:
                                    values.append(val)
                            
                            cursor.execute(insert_sql, tuple(values))
                            upserted_count += 1

                        except Exception as e:
                            error_count += 1
                            print(f"  [Error Fila #{record_count}] No se pudo procesar el registro en '{table_name}'. Causa: {e}")
                            print(f"  [Error Fila #{record_count}] Datos problemáticos: {dict(rec)}")
                    
                    print(f"  Sincronización de '{table_name}' finalizada.")
                    print(f"  Registros leídos: {record_count}, Omitidos(<2023): {skipped_count}, Procesados: {upserted_count}, Errores: {error_count}.")

                except FileNotFoundError:
                    print(f"  [Error Fatal] Archivo no encontrado: {dbf_path}. Saltando tabla '{table_name}'.")
                except Exception as e:
                    print(f"  [Error Fatal] Ocurrió un error inesperado procesando la tabla '{table_name}'. Causa: {e}")

        conn.commit()
        print("\n¡Sincronización por actualización completada! Todos los cambios han sido guardados.")

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
    update_dbfs_to_postgres()
