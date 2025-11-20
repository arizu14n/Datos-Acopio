# app.py

from flask import Flask, render_template, request, Response, redirect, url_for, jsonify
import subprocess
from dbfread import DBF
from collections import OrderedDict
from fpdf import FPDF
import datetime
import os
import locale
from decimal import Decimal
import math
import requests
from bs4 import BeautifulSoup
import sys
import psycopg2
from psycopg2.extras import DictCursor
from dateutil.relativedelta import relativedelta

# --- CONFIGURACIÓN DE LOCALIZACIÓN PARA FORMATO DE NÚMEROS ---
try:
    locale.setlocale(locale.LC_ALL, 'es_AR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'Spanish_Argentina.1252')
    except locale.Error:
        print("Advertencia: No se pudo establecer la localización a es_AR. Los formatos de número pueden ser incorrectos.")

app = Flask(__name__)

# --- CONFIGURACIÓN DE LA BASE DE DATOS POSTGRESQL ---
DB_NAME = "acopio_db"
DB_USER = "user"
DB_PASS = "password"
DB_HOST = "localhost"
DB_PORT = "5432"

def get_db():
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

def get_dict_cursor(conn):
    """Devuelve un cursor que devuelve diccionarios."""
    return conn.cursor(cursor_factory=DictCursor)

@app.route('/sync-db', methods=['POST'])
def sync_db():
    """
    Endpoint para ejecutar el script de sincronización de la base de datos.
    """
    try:
        # Ruta al ejecutable de Python en el entorno virtual
        python_executable = sys.executable
        
        # Ejecuta el script sync_db.py usando el mismo intérprete de Python
        # que está corriendo la aplicación Flask.
        result = subprocess.run(
            [python_executable, 'sync_db.py'],
            capture_output=True,
            text=True,
            check=True  # Lanza una excepción si el script devuelve un error
        )
        
        print(result.stdout) # Muestra la salida del script en la consola del servidor
        return jsonify({'status': 'success', 'message': 'Sincronización completada exitosamente.'})

    except subprocess.CalledProcessError as e:
        # Si el script falla, captura el error
        print(f"Error durante la sincronización: {e.stderr}")
        return jsonify({'status': 'error', 'message': f'Error durante la sincronización: {e.stderr}'}), 500
    except Exception as e:
        # Otros errores inesperados
        print(f"Error inesperado: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Ocurrió un error inesperado: {str(e)}'}), 500



def format_date(date_obj):
    if date_obj is None:
        return ""
    if isinstance(date_obj, datetime.date):
        return date_obj.strftime('%d/%m/%Y')
    return date_obj

def get_grano_description(grano_code, cursor=None):
    """Obtiene la descripción de un grano usando un cursor existente."""
    if not grano_code or not cursor:
        return grano_code
    try:
        cursor.execute("SELECT G_DESC FROM acogran WHERE G_CODI = %s", (grano_code,))
        result = cursor.fetchone()
        return result['g_desc'] if result else grano_code
    except Exception as e:
        print(f"Error al leer la descripción del grano desde PostgreSQL: {e}")
        return grano_code

def format_number(value, is_currency=False, decimals=0):
    """Una función robusta para formatear números."""
    if value is None:
        return ""

    if not isinstance(value, (int, float, Decimal)):
        try:
            if isinstance(value, str) and value.strip() == '':
                value = 0.0
            value = float(value)
        except (ValueError, TypeError):
            return value

    try:
        if is_currency:
            return locale.currency(value, symbol='$ ', grouping=True)
        else:
            return locale.format_string(f"%.{decimals}f", value, grouping=True)
    except Exception:
        return value

app.jinja_env.globals.update(format_number=format_number)
app.jinja_env.globals.update(format_date=format_date)

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, self.title, 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    def create_table(self, table_data, headers, totals=None):
        self.set_font('Arial', 'B', 8)
        
        available_width = self.w - 2 * self.l_margin
        col_width = available_width / len(headers)

        for header in headers:
            self.cell(col_width, 10, header, 1, 0, 'C')
        self.ln()

        self.set_font('Arial', '', 8)
        for row in table_data:
            # Set fill color for not confirmed rows
            if not row.get('confirmed', True):
                self.set_fill_color(240, 240, 240) # light grey
                fill = True
            else:
                fill = False

            # Create a copy of the row to avoid modifying the original
            row_copy = row.copy()
            row_copy.pop('confirmed', None) # Remove confirmed key

            for header in headers:
                item = row_copy.get(header, '')
                item = str(item).encode('latin-1', 'replace').decode('latin-1')
                self.cell(col_width, 10, item, 1, 0, 'L', fill)
            self.ln()

        if totals:
            self.set_font('Arial', 'B', 8)
            if totals['type'] == 'entregas':
                # Subtotal No Confirmadas
                self.cell(col_width * 3, 10, 'Total No Confirmadas', 1, 0, 'C')
                self.cell(col_width, 10, totals['total_no_confirmadas'], 1, 0, 'L')
                self.cell(col_width, 10, f"Reg: {totals['registros_no_confirmadas']}", 1, 0, 'L')
                self.ln()
                # Subtotal Confirmadas
                self.cell(col_width * 3, 10, 'Total Confirmadas', 1, 0, 'C')
                self.cell(col_width, 10, totals['total_confirmadas'], 1, 0, 'L')
                self.cell(col_width, 10, f"Reg: {totals['registros_confirmadas']}", 1, 0, 'L')
                self.ln()
                # Grand Total
                self.cell(col_width * 3, 10, 'Total General', 1, 0, 'C')
                self.cell(col_width, 10, totals['total_general'], 1, 0, 'L')
                self.cell(col_width, 10, f"Reg: {totals['registros_general']}", 1, 0, 'L')

            elif totals['type'] == 'liquidaciones':
                self.cell(col_width * 2, 10, 'Totales', 1, 0, 'C')
                self.cell(col_width, 10, totals['sums']['Peso'], 1, 0, 'L')
                self.cell(col_width, 10, '', 1, 0, 'L')
                self.cell(col_width, 10, totals['sums']['N.Grav.'], 1, 0, 'L')
                self.cell(col_width, 10, totals['sums']['IVA'], 1, 0, 'L')
                self.cell(col_width, 10, totals['sums']['Otros'], 1, 0, 'L')
                self.cell(col_width, 10, totals['sums']['Total'], 1, 0, 'L')
            self.ln()

@app.route('/sync-db-page')
def sync_db_page():
    return render_template('sync_db.html')

@app.route('/')
def home():
    return render_template('home.html')


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    try:
        filtros_aplicados = {}
        if request.method == 'POST':
            filtros_aplicados['fecha_desde'] = request.form.get('fecha_desde')
            filtros_aplicados['fecha_hasta'] = request.form.get('fecha_hasta')
        else:
            today = datetime.date.today()
            first_day_of_month = today.replace(day=1)
            filtros_aplicados['fecha_desde'] = first_day_of_month.strftime('%Y-%m-%d')
            filtros_aplicados['fecha_hasta'] = today.strftime('%Y-%m-%d')

        fecha_desde_dt = datetime.datetime.strptime(filtros_aplicados['fecha_desde'], '%Y-%m-%d').date()
        fecha_hasta_dt = datetime.datetime.strptime(filtros_aplicados['fecha_hasta'], '%Y-%m-%d').date()

        # --- Lógica para Panel de Fletes ---
        fletes_data = None
        conn = get_db()
        if conn:
            try:
                with get_dict_cursor(conn) as cursor:
                    query = "SELECT SUM(o_neto) as total_neto, SUM(importe) as total_importe, COUNT(*) as total_viajes, SUM(g_kilomet) as total_km FROM fletes WHERE g_fecha >= %s AND g_fecha <= %s"
                    cursor.execute(query, (filtros_aplicados['fecha_desde'], filtros_aplicados['fecha_hasta']))
                    fletes_result = cursor.fetchone()
                    if fletes_result:
                        fletes_data = {
                            'toneladas_transportadas': (fletes_result['total_neto'] or 0) / 1000,
                            'monto_facturado': fletes_result['total_importe'] or 0,
                            'cantidad_viajes': fletes_result['total_viajes'] or 0,
                            'kilometros_recorridos': fletes_result['total_km'] or 0
                        }
            finally:
                conn.close()

        # --- Lógica para Panel de Ventas ---
        ventas_por_grano = {}
        total_liquidado_kilos = 0
        total_liquidado_monto = 0

        conn = get_db()
        if conn:
            try:
                with get_dict_cursor(conn) as cursor:
                    # Toneladas Entregadas (acocarpo table)
                    cursor.execute("SELECT g_codi, g_saldo FROM acocarpo WHERE g_fecha >= %s AND g_fecha <= %s", (fecha_desde_dt, fecha_hasta_dt))
                    for rec in cursor.fetchall():
                        grano_code = rec.get('g_codi')
                        if not grano_code: continue
                        grano_desc = get_grano_description(grano_code, cursor)
                        kilos = rec.get('g_saldo', 0) or 0
                        if grano_desc not in ventas_por_grano:
                            ventas_por_grano[grano_desc] = {'toneladas_entregadas': 0}
                        ventas_por_grano[grano_desc]['toneladas_entregadas'] += kilos

                    # Toneladas y Monto Liquidado (liqven table) - Total en el período
                    cursor.execute("SELECT peso, net_cta FROM liqven WHERE fec_c >= %s AND fec_c <= %s", (fecha_desde_dt, fecha_hasta_dt))
                    for rec in cursor.fetchall():
                        total_liquidado_kilos += rec.get('peso', 0) or 0
                        total_liquidado_monto += rec.get('net_cta', 0) or 0
            finally:
                conn.close()
        
        total_liquidado_toneladas = total_liquidado_kilos / 1000

        # Combinar datos para la tabla
        ventas_data = []
        for grano, data in sorted(ventas_por_grano.items()):
            ventas_data.append({
                'grano': grano,
                'toneladas_entregadas': data['toneladas_entregadas'] / 1000
            })

        # --- Lógica para Tabla de Stock y Pendiente ---
        conn = get_db()
        if conn:
            try:
                with get_dict_cursor(conn) as cursor:
                    stock_granos_cosecha = get_stock_granos_por_cosecha(cursor)
                    _, totales_por_grano_cosecha_stock = get_contratos_pendientes(cursor)
            finally:
                conn.close()

        current_year = datetime.date.today().year
        min_harvest_year_start = (current_year - 1) % 100
        min_harvest_year = f"{min_harvest_year_start:02d}/{(min_harvest_year_start + 1):02d}"

        all_keys = set(stock_granos_cosecha.keys()) | set(totales_por_grano_cosecha_stock.keys())

        stock_data = []
        for grano, cosecha in all_keys:
            if cosecha >= min_harvest_year:
                stock = stock_granos_cosecha.get((grano, cosecha), 0)
                pendiente_data = totales_por_grano_cosecha_stock.get((grano, cosecha), {'kilos': 0})
                pendiente = pendiente_data['kilos']
                
                if stock > 0 or pendiente > 0:
                    # Convert stock to float for consistent type operation and handle division by zero
                    porcentaje_afectado = (pendiente / float(stock)) * 100 if float(stock) > 0 else (100 if pendiente > 0 else 0)

                    stock_data.append({
                        'grano': grano,
                        'cosecha': cosecha,
                        'stock': float(stock) / 1000, # Also convert here for consistency
                        'pendiente': pendiente / 1000,
                        'porcentaje_afectado': porcentaje_afectado
                    })

        # --- Lógica para Panel de Cobranzas ---
        cobranzas_data = None
        vencimientos = 0
        cobrado = 0
        conn = get_db()
        if conn:
            try:
                with get_dict_cursor(conn) as cursor:
                    cursor.execute("SELECT tip_f, imp_f FROM ccbcta WHERE vto_f >= %s AND vto_f <= %s", (fecha_desde_dt, fecha_hasta_dt))
                    for rec in cursor.fetchall():
                        tip_f = rec.get('tip_f', '').strip().upper()
                        imp_f = rec.get('imp_f', 0) or 0
                        
                        if tip_f in ('LF', 'LP'):
                            vencimientos += imp_f
                        elif tip_f in ('RI', 'SI', 'SG', 'SB'):
                            cobrado += imp_f
                
                cobranzas_data = {
                    'vencimientos': vencimientos,
                    'cobrado': cobrado,
                    'saldo': vencimientos - cobrado
                }
            except Exception as e:
                print(f"Error al leer cobranzas desde PostgreSQL: {e}")
                cobranzas_data = {'vencimientos': 0, 'cobrado': 0, 'saldo': 0}
            finally:
                if conn:
                    conn.close()
        else:
            cobranzas_data = {'vencimientos': 0, 'cobrado': 0, 'saldo': 0}

        # --- Lógica para Panel de Compras ---
        compras_data = []
        conn = get_db()
        if conn:
            try:
                with get_dict_cursor(conn) as cursor:
                    query = """
                        SELECT 
                            a.g_codi, 
                            g.g_desc, 
                            SUM(a.o_neto) as total_kilos, 
                            COUNT(*) as movimientos
                        FROM acohis a
                        JOIN acogran g ON a.g_codi = g.g_codi
                        WHERE a.g_ctl = 'I' AND a.g_fecha BETWEEN %s AND %s
                        GROUP BY a.g_codi, g.g_desc
                        ORDER BY g.g_desc
                    """
                    cursor.execute(query, (fecha_desde_dt, fecha_hasta_dt))
                    compras_raw = cursor.fetchall()
                    for row in compras_raw:
                        compras_data.append({
                            'grano': row['g_desc'],
                            'kilos': row['total_kilos'],
                            'movimientos': row['movimientos']
                        })
            except Exception as e:
                print(f"Error al leer compras desde PostgreSQL: {e}")
            finally:
                if conn:
                    conn.close()

        # --- Lógica para Tarjeta de Vencimientos ---
        vencimientos_hoy = {'total': 0, 'pendientes': 0}
        conn = get_db()
        if conn:
            try:
                with get_dict_cursor(conn) as cursor:
                    today = datetime.date.today()
                    cursor.execute(
                        "SELECT COUNT(*) as total, SUM(CASE WHEN completada = FALSE THEN 1 ELSE 0 END) as pendientes FROM agenda WHERE fecha_vencimiento = %s",
                        (today,)
                    )
                    result = cursor.fetchone()
                    if result:
                        vencimientos_hoy['total'] = result['total'] or 0
                        vencimientos_hoy['pendientes'] = result['pendientes'] or 0
            except Exception as e:
                print(f"Error al leer vencimientos de la agenda desde PostgreSQL: {e}")
            finally:
                if conn:
                    conn.close()

        return render_template('dashboard.html',
                               filtros_aplicados=filtros_aplicados,
                               fletes_data=fletes_data,
                               ventas_data=ventas_data,
                               total_liquidado_toneladas=total_liquidado_toneladas,
                               total_liquidado_monto=total_liquidado_monto,
                               stock_data=stock_data,
                               cobranzas_data=cobranzas_data,
                               compras_data=compras_data,
                               vencimientos_hoy=vencimientos_hoy)
    except Exception as e:
        # For debugging purposes, returning the error to the page can be helpful
        import traceback
        return f"<h1>Ocurrió un error en el Dashboard: {e}</h1><pre>{traceback.format_exc()}</pre>"

def get_stock_granos_por_cosecha(cursor):
    """Obtiene el stock de granos por cosecha usando un cursor existente."""
    stock_granos = {}
    try:
        cursor.execute("SELECT g_codi, g_cose, g_stok FROM acograst")
        for rec in cursor.fetchall():
            grano_code = rec.get('g_codi')
            cosecha = rec.get('g_cose')
            stock = rec.get('g_stok', 0)
            if grano_code and cosecha:
                grano_desc = get_grano_description(grano_code, cursor)
                stock_granos[(grano_desc, cosecha)] = stock
    except Exception as e:
        print(f"Error al leer el stock de granos desde PostgreSQL: {e}")
    return stock_granos

def get_contratos_pendientes(cursor, min_harvest_year=None):
    """Obtiene los contratos pendientes usando un cursor existente."""
    contratos_pendientes = []
    totales_por_grano_cosecha = {}

    conn = get_db()
    try:
        # Pre-calcular la suma de 'Peso' desde liqven por contrato
        liquidaciones_por_contrato = {}
        cursor.execute("SELECT contrato, peso FROM liqven")
        for rec in cursor.fetchall():
            contrato_liq = rec.get('contrato')
            if contrato_liq and isinstance(contrato_liq, str):
                contrato_liq = contrato_liq.strip()

            peso_liq = float(rec.get('peso', 0) or 0)
            if contrato_liq:
                liquidaciones_por_contrato[contrato_liq] = liquidaciones_por_contrato.get(contrato_liq, 0) + peso_liq

        cursor.execute("SELECT nrocont_c, kiloped_c, entrega_c, liquiya_c, cosecha_c, product_c, apelcom_c FROM contrat")
        for i, rec in enumerate(cursor.fetchall()):
            kiloped = 0.0
            entrega = 0.0
            liquiya = 0.0

            try:
                kiloped = float(rec.get('kiloped_c', 0) or 0)
                entrega = float(rec.get('entrega_c', 0) or 0)
                liquiya = float(rec.get('liquiya_c', 0) or 0)
            except (ValueError, TypeError) as e:
                print(f"ERROR: Could not convert values to float for record {i}: {e}. Record data: {rec}")
                continue

            if (entrega == liquiya and entrega != 0):
                continue

            if kiloped > entrega:
                cosecha = rec.get('cosecha_c', 'N/A')
                if min_harvest_year and cosecha < min_harvest_year:
                    continue

                diferencia = kiloped - entrega
                contrato = rec.get('nrocont_c', 'N/A')
                if isinstance(contrato, str):
                    contrato = contrato.strip()

                grano_desc = rec.get('product_c', 'N/A')
                comprador = rec.get('apelcom_c', 'N/A')
                camiones = math.ceil(diferencia / 30000)

                kilos_liq_ventas = liquidaciones_por_contrato.get(contrato, 0)

                contrato_info = {
                    'contrato': contrato,
                    'comprador': comprador,
                    'grano': grano_desc,
                    'cosecha': cosecha,
                    'kilos_pendientes': format_number(diferencia),
                    'camiones_pendientes': camiones,
                    'kilos_solicitados': format_number(kiloped),
                    'kilos_entregados': format_number(entrega),
                    'kilos_liquidados': format_number(liquiya),
                    'kilos_liq_ventas': kilos_liq_ventas
                }
                contratos_pendientes.append(contrato_info)

                if (grano_desc, cosecha) not in totales_por_grano_cosecha:
                    totales_por_grano_cosecha[(grano_desc, cosecha)] = {'kilos': 0, 'camiones': 0, 'kilos_liquidados': 0, 'kilos_liq_ventas': 0}
                
                totales_por_grano_cosecha[(grano_desc, cosecha)]['kilos'] += diferencia
                totales_por_grano_cosecha[(grano_desc, cosecha)]['camiones'] += camiones
                totales_por_grano_cosecha[(grano_desc, cosecha)]['kilos_liquidados'] += liquiya
                totales_por_grano_cosecha[(grano_desc, cosecha)]['kilos_liq_ventas'] += kilos_liq_ventas
    except Exception as e:
        print(f"Error al leer contratos pendientes desde PostgreSQL: {e}")

    return contratos_pendientes, totales_por_grano_cosecha



@app.route('/ventas', methods=['GET', 'POST'])
def ventas():
    try:
        totales_por_grano = {}
        pie_chart_labels = []
        pie_chart_values = []
        bar_chart_labels = []
        bar_chart_pendientes = []
        bar_chart_stock = []
        contratos_pendientes = []

        conn = get_db()
        if conn:
            try:
                with get_dict_cursor(conn) as cursor:
                    # --- New section for pending contracts ---
                    current_year = datetime.date.today().year
                    min_harvest_year_start = (current_year - 1) % 100
                    min_harvest_year = f"{min_harvest_year_start:02d}/{(min_harvest_year_start + 1):02d}"
                    contratos_pendientes, totales_por_grano_cosecha = get_contratos_pendientes(cursor, min_harvest_year=min_harvest_year)
                    stock_granos_cosecha = get_stock_granos_por_cosecha(cursor)

                    # Prepare data for pie chart (pending shipments by grain)
                    if totales_por_grano_cosecha:
                        for (grano, cosecha), data in totales_por_grano_cosecha.items():
                            if grano not in totales_por_grano:
                                totales_por_grano[grano] = {'kilos': 0, 'camiones': 0}
                            totales_por_grano[grano]['kilos'] += data['kilos']
                            totales_por_grano[grano]['camiones'] += data['camiones']
                        
                    pie_chart_labels = list(totales_por_grano.keys())
                    pie_chart_values = [totales_por_grano[key]['kilos'] for key in pie_chart_labels]

                    # Prepare data for bar chart (pending vs stock by grain and harvest)
                    bar_chart_labels = [f"{grano} ({cosecha})" for (grano, cosecha) in totales_por_grano_cosecha.keys()]
                    bar_chart_pendientes = [data['kilos'] for data in totales_por_grano_cosecha.values()]
                    bar_chart_stock = [stock_granos_cosecha.get((grano, cosecha), 0) for (grano, cosecha) in totales_por_grano_cosecha.keys()]
            finally:
                conn.close()

        if totales_por_grano_cosecha:
            for (grano, cosecha), data in totales_por_grano_cosecha.items():
                if grano not in totales_por_grano:
                    totales_por_grano[grano] = {'kilos': 0, 'camiones': 0}
                totales_por_grano[grano]['kilos'] += data['kilos']
                totales_por_grano[grano]['camiones'] += data['camiones']
            
        pie_chart_labels = list(totales_por_grano.keys())
        pie_chart_values = [totales_por_grano.get(key, {}).get('kilos', 0) for key in pie_chart_labels]

        # --- Cupos Solicitados ---
        conn = get_db()
        if not conn:
            return "<h1>Error: No se pudo conectar a la base de datos.</h1>"
        
        try:
            with get_dict_cursor(conn) as cursor:
                cursor.execute("SELECT * FROM cupos_solicitados WHERE flete_id IS NULL ORDER BY fecha_solicitud DESC")
                cupos_solicitados = cursor.fetchall()

                cursor.execute("SELECT * FROM fletes ORDER BY g_fecha DESC")
                fletes = cursor.fetchall()

                totales_cupos_por_grano = {}
                for cupo in cupos_solicitados:
                    grano = cupo['grano']
                    cantidad = cupo['cantidad']
                    if grano not in totales_cupos_por_grano:
                        totales_cupos_por_grano[grano] = 0
                    totales_cupos_por_grano[grano] += cantidad

                # --- Existing logic for contract selection ---
                latest_dates = {}
                cursor.execute("SELECT g_contrato, MAX(g_fecha) as max_fecha FROM acocarpo WHERE g_contrato IS NOT NULL AND g_fecha IS NOT NULL GROUP BY g_contrato")
                for rec in cursor.fetchall():
                    latest_dates[rec['g_contrato']] = rec['max_fecha']
                
                contratos_ordenados = sorted(latest_dates.keys(), key=lambda c: latest_dates[c], reverse=True)

                g_contrato_filtro = None
                info_adicional = None
                total_saldo_num = 0
                total_peso = 0
                
                entregas_confirmadas = []
                entregas_no_confirmadas = []
                total_confirmadas_num = 0
                total_no_confirmadas_num = 0
                
                liquidaciones_filtradas = None
                total_liquidaciones = 0
                diferencia = 0
                totales_liq_formatted = {}
                camiones_restantes = 0

                if request.method == 'POST':
                    g_contrato_filtro = request.form.get('g_contrato')
                    if g_contrato_filtro:
                        cursor.execute("SELECT * FROM acocarpo WHERE g_contrato = %s", (g_contrato_filtro,))
                        registros_acocarpo = cursor.fetchall()
                        
                        if registros_acocarpo:
                            for rec in registros_acocarpo:
                                registro_ordenado = OrderedDict()
                                registro_ordenado['FECHA'] = format_date(rec.get('g_fecha', ''))
                                registro_ordenado['Nro Interno'] = rec.get('g_roman', '')
                                registro_ordenado['CTG'] = rec.get('g_ctg', '')
                                registro_ordenado['Kilos Netos'] = format_number(rec.get('g_saldo', 0))
                                registro_ordenado['DESTINO'] = rec.get('g_destino', '')
                                
                                if rec.get('g_confirm', 'N').strip().upper() == 'S':
                                    entregas_confirmadas.append(registro_ordenado)
                                    total_confirmadas_num += rec.get('g_saldo', 0) or 0
                                else:
                                    entregas_no_confirmadas.append(registro_ordenado)
                                    total_no_confirmadas_num += rec.get('g_saldo', 0) or 0

                            total_saldo_num = total_confirmadas_num + total_no_confirmadas_num
                            
                            info_adicional = {
                                'grano': registros_acocarpo[0].get('g_codi', 'N/A'),
                                'cosecha': registros_acocarpo[0].get('g_cose', 'N/A')
                            }
                            grano_code = info_adicional['grano']
                            info_adicional['grano'] = get_grano_description(grano_code, cursor)

                        cursor.execute("SELECT * FROM liqven WHERE contrato = %s", (g_contrato_filtro,))
                        registros_liqven = cursor.fetchall()

                        if registros_liqven:
                            if info_adicional:
                                info_adicional['comprador'] = registros_liqven[0].get('nom_c', 'N/A')
                            
                            liquidaciones_filtradas = []
                            sumas = { 'Peso': 0, 'N.Grav.': 0, 'IVA': 0, 'Otros': 0, 'Total': 0 }

                            for rec in registros_liqven:
                                fac_c_padded = str(rec.get('fac_c', '')).zfill(8)
                                coe_val = f"{rec.get('fa1_c', '')}-{fac_c_padded}"
                                
                                otros_val_num = sum(rec.get(col, 0) or 0 for col in ['otr_gas', 'iva_gas', 'gas_com', 'iva_com', 'gas_var', 'iva_var'])

                                sumas['Peso'] += rec.get('peso', 0) or 0
                                sumas['N.Grav.'] += rec.get('bru_c', 0) or 0
                                sumas['IVA'] += rec.get('iva_c', 0) or 0
                                sumas['Otros'] += otros_val_num
                                sumas['Total'] += rec.get('net_cta', 0) or 0

                                liquidacion_ordenada = OrderedDict()
                                liquidacion_ordenada['Fecha'] = format_date(rec.get('fec_c', ''))
                                liquidacion_ordenada['COE'] = coe_val
                                liquidacion_ordenada['Peso'] = format_number(rec.get('peso', 0))
                                liquidacion_ordenada['Precio'] = format_number(rec.get('preope', 0), is_currency=True)
                                liquidacion_ordenada['N.Grav.'] = format_number(rec.get('bru_c', 0), is_currency=True)
                                liquidacion_ordenada['IVA'] = format_number(rec.get('iva_c', 0), is_currency=True)
                                liquidacion_ordenada['Otros'] = format_number(otros_val_num, is_currency=True)
                                liquidacion_ordenada['Total'] = format_number(rec.get('net_cta', 0), is_currency=True)
                                liquidaciones_filtradas.append(liquidacion_ordenada)
                            
                            total_liquidaciones = len(registros_liqven)
                            totales_liq_formatted = {key: format_number(val, is_currency=(key != 'Peso')) for key, val in sumas.items()}
                            total_peso = sumas['Peso']
                    
                    diferencia = total_saldo_num - total_peso
                    if diferencia < 0:
                        camiones_restantes = math.ceil(abs(diferencia) / 30000)
        finally:
            if conn:
                conn.close()

        return render_template('index.html', 
                               contratos_pendientes=contratos_pendientes,
                               totales_por_grano=totales_por_grano,
                               pie_chart_labels=pie_chart_labels,
                               pie_chart_values=pie_chart_values,
                               bar_chart_labels=bar_chart_labels,
                               bar_chart_pendientes=bar_chart_pendientes,
                               bar_chart_stock=bar_chart_stock,
                               cupos_solicitados=cupos_solicitados,
                               fletes=fletes,
                               totales_cupos_por_grano=totales_cupos_por_grano,
                               contratos=contratos_ordenados,
                               entregas_confirmadas=entregas_confirmadas,
                               entregas_no_confirmadas=entregas_no_confirmadas,
                               g_contrato_filtro=g_contrato_filtro,
                               info_adicional=info_adicional,
                               total_confirmadas=format_number(total_confirmadas_num),
                               total_no_confirmadas=format_number(total_no_confirmadas_num),
                               registros_confirmadas=len(entregas_confirmadas),
                               registros_no_confirmadas=len(entregas_no_confirmadas),
                               total_saldo=format_number(total_saldo_num),
                               total_registros=len(entregas_confirmadas) + len(entregas_no_confirmadas),
                               liquidaciones_filtradas=liquidaciones_filtradas,
                               total_liquidaciones=total_liquidaciones,
                               totales_liq=totales_liq_formatted, 
                               diferencia=format_number(diferencia),
                               diferencia_num=diferencia,
                               camiones_restantes=camiones_restantes,
                               total_saldo_num=total_saldo_num,
                               total_peso_num=total_peso)

    except FileNotFoundError as e:
        return f"<h1>Error: No se encontró el archivo DBF: {e.filename}</h1>"
    except Exception as e:
        return f"<h1>Ocurrió un error al leer el archivo: {e}</h1>"

@app.route('/compras', methods=['GET', 'POST'])
def compras():
    conn = get_db()
    if not conn:
        return "<h1>Error: No se pudo conectar a la base de datos.</h1>"

    try:
        with get_dict_cursor(conn) as cursor:
            # --- Obtener valores para los filtros ---
            cursor.execute("SELECT DISTINCT g_codi FROM acohis WHERE g_ctl = 'I' AND g_codi IS NOT NULL")
            grano_codes = [row['g_codi'] for row in cursor.fetchall()]
            
            granos = {}
            if grano_codes:
                cursor.execute("SELECT g_codi, g_desc FROM acogran WHERE g_codi IN %s", (tuple(grano_codes),))
                for rec in cursor.fetchall():
                    granos[rec['g_codi']] = rec['g_desc'].strip()

            cursor.execute("SELECT DISTINCT g_cose FROM acohis WHERE g_ctl = 'I' AND g_cose IS NOT NULL ORDER BY g_cose DESC")
            cosechas = [row['g_cose'] for row in cursor.fetchall()]

            cursor.execute("SELECT DISTINCT cli_c FROM acohis WHERE g_ctl = 'I' AND cli_c IS NOT NULL")
            vendedor_codes = [row['cli_c'] for row in cursor.fetchall()]
            
            vendedores = {}
            if vendedor_codes:
                cursor.execute("SELECT cli_c, s_apelli FROM sysmae WHERE cli_c IN %s", (tuple(vendedor_codes),))
                for rec in cursor.fetchall():
                    vendedores[rec['cli_c']] = rec['s_apelli'].strip()

            cursor.execute("SELECT DISTINCT g_ctaplade FROM acohis WHERE g_ctl = 'I' AND g_ctaplade IS NOT NULL")
            origen_codes = [row['g_ctaplade'] for row in cursor.fetchall()]

            origenes = {}
            if origen_codes:
                cursor.execute("SELECT cli_c, s_locali FROM sysmae WHERE cli_c IN %s", (tuple(origen_codes),))
                for rec in cursor.fetchall():
                    origenes[rec['cli_c']] = rec['s_locali'].strip()

            # --- Procesar filtros ---
            filtros_aplicados = {}
            query = "SELECT * FROM acohis WHERE g_ctl = 'I'"
            params = []

            if request.method == 'POST':
                filtros_aplicados['fecha_desde'] = request.form.get('fecha_desde')
                filtros_aplicados['fecha_hasta'] = request.form.get('fecha_hasta')
                filtros_aplicados['vendedor'] = request.form.get('vendedor')
                filtros_aplicados['grano'] = request.form.get('grano')
                filtros_aplicados['cosecha'] = request.form.get('cosecha')
                filtros_aplicados['origen'] = request.form.get('origen')
            else:
                today = datetime.date.today()
                first_day_of_month = today.replace(day=1)
                filtros_aplicados['fecha_desde'] = first_day_of_month.strftime('%Y-%m-%d')
                filtros_aplicados['fecha_hasta'] = today.strftime('%Y-%m-%d')

            if filtros_aplicados.get('fecha_desde'):
                query += " AND g_fecha >= %s"
                params.append(filtros_aplicados['fecha_desde'])
            if filtros_aplicados.get('fecha_hasta'):
                query += " AND g_fecha <= %s"
                params.append(filtros_aplicados['fecha_hasta'])
            if filtros_aplicados.get('vendedor'):
                query += " AND cli_c = %s"
                params.append(filtros_aplicados['vendedor'])
            if filtros_aplicados.get('grano'):
                query += " AND g_codi = %s"
                params.append(filtros_aplicados['grano'])
            if filtros_aplicados.get('cosecha'):
                query += " AND g_cose = %s"
                params.append(filtros_aplicados['cosecha'])
            if filtros_aplicados.get('origen'):
                query += " AND g_ctaplade = %s"
                params.append(filtros_aplicados['origen'])
            
            query += " ORDER BY g_fecha DESC"
            cursor.execute(query, params)
            compras_data = cursor.fetchall()

            # --- Procesar datos para la tabla y calcular totales ---
            tabla_compras = []
            total_kilos_brutos = 0
            total_mermas = 0
            total_kilos_netos = 0

            for compra in compras_data:
                kilos_brutos = compra.get('o_peso', 0) or 0
                kilos_netos = compra.get('o_neto', 0) or 0
                mermas = kilos_brutos - kilos_netos

                total_kilos_brutos += kilos_brutos
                total_mermas += mermas
                total_kilos_netos += kilos_netos

                tabla_compras.append({
                    'fecha': format_date(compra.get('g_fecha')),
                    'ctg': compra.get('g_ctg', ''),
                    'vendedor': vendedores.get(compra.get('cli_c'), ''),
                    'grano': granos.get(compra.get('g_codi'), ''),
                    'cosecha': compra.get('g_cose', ''),
                    'origen': origenes.get(compra.get('g_ctaplade'), ''),
                    'kilos_brutos': format_number(kilos_brutos, decimals=2),
                    'mermas': format_number(mermas, decimals=2),
                    'kilos_netos': format_number(kilos_netos, decimals=2)
                })
            
            record_count = len(compras_data)
            totales = {
                'registros': format_number(record_count, decimals=0),
                'kilos_brutos': format_number(total_kilos_brutos, decimals=2),
                'mermas': format_number(total_mermas, decimals=2),
                'kilos_netos': format_number(total_kilos_netos, decimals=2)
            }

            return render_template('compras.html',
                                   compras=tabla_compras,
                                   filtros_aplicados=filtros_aplicados,
                                   vendedores=vendedores,
                                   granos=granos,
                                   cosechas=cosechas,
                                   origenes=origenes,
                                   totales=totales)
    except Exception as e:
        import traceback
        return f"<h1>Ocurrió un error en Compras: {e}</h1><pre>{traceback.format_exc()}</pre>"
    finally:
        if conn:
            conn.close()

@app.route('/cupos/solicitar', methods=['POST'])
def solicitar_cupo():
    try:
        data = request.json
        num_cupos = int(data['cantidad'])
        cantidad_por_cupo = 1  

        conn = get_db()
        if not conn:
            return jsonify({'success': False, 'error': 'No se pudo conectar a la base de datos.'})
        
        try:
            with get_dict_cursor(conn) as cursor:
                for _ in range(num_cupos):
                    cursor.execute("""
                        INSERT INTO cupos_solicitados (contrato, grano, cosecha, cantidad, fecha_solicitud, nombre_persona)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        data['contrato'],
                        data['grano'],
                        data['cosecha'],
                        cantidad_por_cupo,
                        data['fecha_solicitud'],
                        data['nombre_persona']
                    ))
            conn.commit()
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            if conn:
                conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/cupos/assign_trip', methods=['POST'])
def assign_trip():
    try:
        data = request.json
        conn = get_db()
        if not conn:
            return jsonify({'success': False, 'error': 'No se pudo conectar a la base de datos.'})
        
        try:
            with get_dict_cursor(conn) as cursor:
                cursor.execute("UPDATE cupos_solicitados SET flete_id = %s WHERE id = %s", (data['flete_id'], data['cupo_id']))
            conn.commit()
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            if conn:
                conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/cupos/update_codigo', methods=['POST'])
def update_codigo():
    try:
        data = request.json
        conn = get_db()
        if not conn:
            return jsonify({'success': False, 'error': 'No se pudo conectar a la base de datos.'})
        
        try:
            with get_dict_cursor(conn) as cursor:
                cursor.execute("UPDATE cupos_solicitados SET codigo_cupo = %s WHERE id = %s", (data['codigo_cupo'], data['cupo_id']))
            conn.commit()
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            if conn:
                conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/cupos/delete/<int:cupo_id>', methods=['POST'])
def delete_cupo(cupo_id):
    try:
        conn = get_db()
        if not conn:
            return jsonify({'success': False, 'error': 'No se pudo conectar a la base de datos.'})
        
        try:
            with get_dict_cursor(conn) as cursor:
                cursor.execute("DELETE FROM cupos_solicitados WHERE id = %s", (cupo_id,))
            conn.commit()
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            if conn:
                conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def get_filtro_values():
    granos = {}
    cosechas = set()
    compradores = set()
    
    conn = get_db()
    if not conn:
        return sorted(granos.items()), sorted(list(cosechas), reverse=True), sorted(list(compradores))

    try:
        with get_dict_cursor(conn) as cursor:
            cursor.execute("SELECT g_codi, g_desc FROM acogran")
            for rec in cursor.fetchall():
                if rec.get('g_codi') and rec.get('g_desc'):
                    granos[rec['g_codi']] = rec['g_desc'].strip()

            cursor.execute("SELECT DISTINCT g_cose FROM acocarpo WHERE g_cose IS NOT NULL")
            for rec in cursor.fetchall():
                cosechas.add(rec['g_cose'].strip())
            
            cursor.execute("SELECT DISTINCT apelcom_c FROM contrat WHERE apelcom_c IS NOT NULL")
            for rec in cursor.fetchall():
                compradores.add(rec['apelcom_c'].strip())

    except Exception as e:
        print(f"Ocurrió un error al leer los valores de filtro desde PostgreSQL: {e}")
    finally:
        if conn:
            conn.close()
        
    return sorted(granos.items()), sorted(list(cosechas), reverse=True), sorted(list(compradores))

def get_entregas(filtros):
    entregas = []
    total_kilos_netos = 0
    
    conn = get_db()
    if not conn:
        return entregas, total_kilos_netos

    try:
        with get_dict_cursor(conn) as cursor:
            compradores_map = {}
            cursor.execute("SELECT nrocont_c, apelcom_c FROM contrat")
            for rec in cursor.fetchall():
                compradores_map[rec['nrocont_c'].strip()] = rec['apelcom_c'].strip()

            query = "SELECT * FROM acocarpo WHERE 1=1"
            params = []

            if filtros.get('fecha_desde'):
                query += " AND g_fecha >= %s"
                params.append(datetime.datetime.strptime(filtros['fecha_desde'], '%Y-%m-%d').date())
            if filtros.get('fecha_hasta'):
                query += " AND g_fecha <= %s"
                params.append(datetime.datetime.strptime(filtros['fecha_hasta'], '%Y-%m-%d').date())
            if filtros.get('grano'):
                query += " AND g_codi = %s"
                params.append(filtros['grano'])
            if filtros.get('cosecha'):
                query += " AND g_cose = %s"
                params.append(filtros['cosecha'])
            
            cursor.execute(query, params)

            for rec in cursor.fetchall():
                contrato = rec.get('g_contrato', '').strip()
                nombre_comprador = compradores_map.get(contrato, '')
                if filtros.get('comprador') and nombre_comprador != filtros['comprador']:
                    continue
                
                kilos_netos = rec.get('g_saldo', 0)
                total_kilos_netos += kilos_netos

                entrega = {
                    'fecha': format_date(rec.get('g_fecha')),
                    'contrato': contrato,
                    'comprador': nombre_comprador,
                    'grano': get_grano_description(rec.get('g_codi'), cursor),
                    'cosecha': rec.get('g_cose'),
                    'kilos_netos': format_number(kilos_netos),
                    'ctg': rec.get('g_ctg', ''),
                    'destino': rec.get('g_destino', '')
                }
                entregas.append(entrega)

    except Exception as e:
        print(f"Ocurrió un error al leer las entregas desde PostgreSQL: {e}")
    finally:
        if conn:
            conn.close()

    return entregas, total_kilos_netos

@app.route('/consultas', methods=['GET', 'POST'])
def consultas():
    # --- Lógica para consulta SISA ---
    cuit_to_display = ''
    tabla_sisa = None
    error_sisa = None

    # --- Lógica para consulta de Entregas ---
    entregas = None
    total_kilos_netos = 0
    filtros_aplicados = {}
    
    # --- Lógica para Cuenta Corriente Granaria ---
    cuenta_corriente_data = None
    g_contrato_filtro_granaria = None


    # --- Obtener valores para los filtros ---
    granos, cosechas, compradores = get_filtro_values()
    
    # --- Obtener todos los contratos para el dropdown de Cta Cte Granaria de las últimas 3 cosechas ---
    contratos_granaria = []
    conn = get_db()
    if conn:
        try:
            with get_dict_cursor(conn) as cursor:
                cursor.execute("SELECT DISTINCT g_cose FROM acocarpo WHERE g_cose IS NOT NULL ORDER BY g_cose DESC")
                cosechas_unicas = [rec['g_cose'] for rec in cursor.fetchall()]
                ultimas_tres_cosechas = cosechas_unicas[:3]

                if ultimas_tres_cosechas:
                    cursor.execute("SELECT DISTINCT g_contrato FROM acocarpo WHERE g_contrato IS NOT NULL AND g_cose IN %s ORDER BY g_contrato DESC", (tuple(ultimas_tres_cosechas),))
                    contratos_granaria = [rec['g_contrato'] for rec in cursor.fetchall()]
        except Exception as e:
            print(f"Error al leer contratos para Cta Cte Granaria desde PostgreSQL: {e}")
        finally:
            conn.close()


    if request.method == 'POST':
        # Determinar qué formulario se envió
        if 'cuit' in request.form:
            cuit = request.form.get('cuit')
            cuit_to_display = cuit # Keep the searched CUIT for display
            url = "https://servicioscf.afip.gob.ar/Registros/sisa/sisa.aspx"
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service as ChromeService
            import time

            driver = None # Initialize driver to None
            try:
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--window-size=1920x1080") # Set a common window size
                chrome_options.add_argument("--disable-dev-shm-usage") # Overcome limited resource problems

                # Use ChromeDriverManager to automatically download and manage the driver
                service = ChromeService(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
                
                driver.get(url)

                # Wait for the CUIT input field to be present
                cuit_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "txtcuit"))
                )
                cuit_input.clear()
                cuit_input.send_keys(cuit)

                # Find and click the "consultar" button
                consultar_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "btnListar"))
                )
                consultar_button.click()

                # Wait for the table to be present and visible
                WebDriverWait(driver, 20).until(
                    EC.visibility_of_element_located((By.ID, "grv"))
                )
                
                # Get the page source after the table has loaded
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                dvtabla_div = soup.find('div', {'id': 'dvtabla'})
                if not dvtabla_div:
                    error_sisa = "No se encontró el contenedor principal de la tabla (div#dvtabla) en la respuesta del navegador."

                else:
                    table = dvtabla_div.find('table', {'id': 'grv'})
                    if not table:
                        error_sisa = "Se encontró el contenedor de la tabla (div#dvtabla), pero no se encontró la tabla (table#grv) dentro."
                    else:
                        headers = []
                        thead = table.find('thead')
                        if thead:
                            headers = [header.text.strip() for header in thead.find_all('th')]
                        else:
                            tbody_for_header_check = table.find('tbody')
                            if tbody_for_header_check:
                                first_row = tbody_for_header_check.find('tr')
                                if first_row:
                                    headers = [cell.text.strip() for cell in first_row.find_all(['th', 'td'])]
                            
                            if not headers:
                                error_sisa = "Se encontró la tabla, pero no se pudo encontrar el encabezado (<thead>) ni extraerlo del cuerpo (<tbody>)."
                        
                        rows = []
                        tbody = table.find('tbody')
                        if tbody:
                            start_row_index = 1 if not thead and headers else 0
                            for row in tbody.find_all('tr')[start_row_index:]:
                                cells = [cell.text.strip() for cell in row.find_all('td')]
                                rows.append(cells)
                        else:
                            error_sisa = "Se encontró la tabla, pero no se pudo encontrar el cuerpo (<tbody>)."
                        
                        if not error_sisa:
                            tabla_sisa = {'headers': headers, 'rows': rows}

            except Exception as e:
                error_sisa = f"Ocurrió un error con Selenium: {e}"
            finally:
                if driver:
                    driver.quit()

        elif 'consultar_entregas' in request.form:
            # --- Procesar formulario de Entregas ---
            filtros = {
                'fecha_desde': request.form.get('fecha_desde'),
                'fecha_hasta': request.form.get('fecha_hasta'),
                'grano': request.form.get('grano'),
                'cosecha': request.form.get('cosecha'),
                'comprador': request.form.get('comprador')
            }
            entregas, total_kilos_netos = get_entregas(filtros)
            filtros_aplicados = filtros
            
        elif 'consultar_granaria' in request.form:
            g_contrato_filtro_granaria = request.form.get('g_contrato_granaria')
            if g_contrato_filtro_granaria:
                movimientos = []
                conn = get_db()
                if conn:
                    try:
                        with get_dict_cursor(conn) as cursor:
                            # Obtener Entregas
                            cursor.execute("SELECT g_fecha, g_ctg, g_saldo FROM acocarpo WHERE g_contrato = %s", (g_contrato_filtro_granaria,))
                            for rec in cursor.fetchall():
                                if isinstance(rec.get('g_fecha'), datetime.date):
                                    movimientos.append({
                                        'fecha': rec['g_fecha'],
                                        'comprobante': rec.get('g_ctg', ''),
                                        'descripcion': f"Entrega - CTG: {rec.get('g_ctg', '')}",
                                        'entregas': rec.get('g_saldo', 0) or 0,
                                        'liquidaciones': 0
                                    })
                            
                            # Obtener Liquidaciones
                            cursor.execute("SELECT fec_c, fac_c, fa1_c, peso FROM liqven WHERE contrato = %s", (g_contrato_filtro_granaria,))
                            for rec in cursor.fetchall():
                                if isinstance(rec.get('fec_c'), datetime.date):
                                    fac_c_padded = str(rec.get('fac_c', '')).zfill(8)
                                    coe_val = f"{rec.get('fa1_c', '')}-{fac_c_padded}"
                                    movimientos.append({
                                        'fecha': rec['fec_c'],
                                        'comprobante': coe_val,
                                        'descripcion': f"Liquidación - COE: {coe_val}",
                                        'entregas': 0,
                                        'liquidaciones': rec.get('peso', 0) or 0
                                    })
                    except Exception as e:
                        print(f"Error al leer Cta Cte Granaria desde PostgreSQL: {e}")
                    finally:
                        conn.close()
                
                # Ordenar movimientos por fecha
                movimientos.sort(key=lambda x: x['fecha'])
                
                # Calcular saldo
                saldo = 0
                cuenta_corriente_data = []
                for mov in movimientos:
                    saldo += mov['entregas'] - mov['liquidaciones']
                    cuenta_corriente_data.append({
                        'fecha': format_date(mov['fecha']),
                        'comprobante': mov['comprobante'],
                        'descripcion': mov['descripcion'],
                        'entregas': format_number(mov['entregas']),
                        'liquidaciones': format_number(mov['liquidaciones']),
                        'saldo': format_number(saldo)
                    })


    return render_template('consultas.html', 
                           cuit_consultado=cuit_to_display,
                           tabla_sisa=tabla_sisa, 
                           error=error_sisa,
                           granos=granos,
                           cosechas=cosechas,
                           compradores=compradores,
                           entregas=entregas,
                           total_kilos_netos=format_number(total_kilos_netos),
                           filtros_aplicados=filtros_aplicados,
                           contratos_granaria=contratos_granaria,
                           g_contrato_filtro_granaria=g_contrato_filtro_granaria,
                           cuenta_corriente_data=cuenta_corriente_data)

@app.route('/cobranzas', methods=['GET', 'POST'])
def cobranzas():
    filtros_aplicados = {}
    if request.method == 'POST':
        filtros_aplicados['fecha_desde'] = request.form.get('fecha_desde')
        filtros_aplicados['fecha_hasta'] = request.form.get('fecha_hasta')
    else:
        today = datetime.date.today()
        first_day_of_month = today.replace(day=1)
        filtros_aplicados['fecha_desde'] = first_day_of_month.strftime('%Y-%m-%d')
        filtros_aplicados['fecha_hasta'] = today.strftime('%Y-%m-%d')

    fecha_desde_dt = datetime.datetime.strptime(filtros_aplicados['fecha_desde'], '%Y-%m-%d').date()
    fecha_hasta_dt = datetime.datetime.strptime(filtros_aplicados['fecha_hasta'], '%Y-%m-%d').date()

    vencimientos_list = []
    cobranzas_list = []
    total_vencimientos = 0
    total_cobranzas = 0

    conn = get_db()
    if not conn:
        return "<h1>Error: No se pudo conectar a la base de datos.</h1>"

    try:
        with get_dict_cursor(conn) as cursor:
            # 1. Mapear Contrato -> Grano desde contrat
            contrato_to_grano = {}
            cursor.execute("SELECT nrocont_c, product_c FROM contrat")
            for rec in cursor.fetchall():
                contrato = rec.get('nrocont_c', '').strip()
                grano = rec.get('product_c', 'N/A').strip()
                if contrato:
                    contrato_to_grano[contrato] = grano

            # 2. Mapear Comprobante de Vencimiento -> Contrato
            comprobante_to_contrato = {}
            cursor.execute("SELECT contrato, fa1_c, fac_c FROM liqven")
            for rec in cursor.fetchall():
                contrato = rec.get('contrato', '').strip()
                if contrato:
                    comprobante = f"{rec.get('fa1_c', '')}-{str(rec.get('fac_c', '')).zfill(8)}"
                    comprobante_to_contrato[comprobante] = contrato

            clientes_map = {}
            cursor.execute("SELECT cli_c, s_apelli FROM sysmae")
            for rec in cursor.fetchall():
                if rec.get('cli_c') and rec.get('s_apelli'):
                    clientes_map[rec['cli_c'].strip()] = rec['s_apelli'].strip()

            # Build a map from vencimiento comprobante to grano
            vencimiento_comprobante_to_grano = {}
            cursor.execute("SELECT tip_f, fa1_f, fac_f FROM ccbcta")
            for rec in cursor.fetchall():
                tip_f = rec.get('tip_f', '').strip().upper()
                if tip_f in ('LF', 'LP'):
                    comprobante = f"{rec.get('fa1_f', '')}-{str(rec.get('fac_f', '')).zfill(8)}"
                    contrato = comprobante_to_contrato.get(comprobante)
                    if contrato:
                        grano = contrato_to_grano.get(contrato, 'N/A')
                        if grano != 'N/A':
                            vencimiento_comprobante_to_grano[comprobante] = grano

            cursor.execute("SELECT * FROM ccbcta WHERE vto_f >= %s AND vto_f <= %s ORDER BY fa1_f, fac_f, vto_f", (fecha_desde_dt, fecha_hasta_dt))
            for rec in cursor.fetchall():
                tip_f = rec.get('tip_f', '').strip().upper()
                imp_f = rec.get('imp_f', 0) or 0
                cliente_code = rec.get('cli_f', '').strip()
                comprobante = f"{rec.get('fa1_f', '')}-{str(rec.get('fac_f', '')).zfill(8)}"

                if tip_f in ('LF', 'LP'):
                    contrato = comprobante_to_contrato.get(comprobante)
                    grano = 'N/A'
                    if contrato:
                        grano = contrato_to_grano.get(contrato, 'N/A')
                    
                    item = {
                        'vencimiento': format_date(rec.get('vto_f')),
                        'cliente': clientes_map.get(cliente_code, cliente_code),
                        'tipo': tip_f,
                        'comprobante': comprobante,
                        'importe': imp_f,
                        'grano': grano
                    }
                    vencimientos_list.append(item)
                    total_vencimientos += imp_f
                elif tip_f in ('RI', 'SI', 'SG', 'SB'):
                    cta_p_comprobante = rec.get('cta_p', '').strip()
                    item = {
                        'vencimiento': format_date(rec.get('vto_f')),
                        'cliente': clientes_map.get(cliente_code, cliente_code),
                        'tipo': tip_f,
                        'comprobante': comprobante,
                        'importe': imp_f,
                        'cta_p': cta_p_comprobante
                    }
                    cobranzas_list.append(item)
                    total_cobranzas += imp_f
    except Exception as e:
        print(f"Error al leer cobranzas desde PostgreSQL: {e}")
    finally:
        if conn:
            conn.close()

    comprobante_sums = {}
    for item in cobranzas_list:
        comprobante = item['comprobante']
        importe = item['importe']
        comprobante_sums[comprobante] = comprobante_sums.get(comprobante, 0) + importe

    for item in cobranzas_list:
        item['total_comprobante'] = comprobante_sums.get(item['comprobante'], 0)

    return render_template('cobranzas.html', 
                           filtros_aplicados=filtros_aplicados,
                           vencimientos=vencimientos_list,
                           cobranzas=cobranzas_list,
                           total_vencimientos=total_vencimientos,
                           total_cobranzas=total_cobranzas,
                           title="Cobranzas")

def importar_fletes_desde_acohis():
    try:
        conn = get_db()
        if not conn:
            return "Error: No se pudo conectar a la base de datos."

        try:
            with get_dict_cursor(conn) as cursor:
                # Se busca en 'V' (Ventas/Salidas) y 'I' (Ingresos) para obtener todos los fletes.
                cursor.execute("SELECT * FROM acohis WHERE g_cuitran = '30-68979922-8' AND g_ctl IN ('V', 'I') AND g_cose >= '20/21'")
                fletes_data = cursor.fetchall()

                added_count = 0
                skipped_count = 0
                updated_count = 0
                for rec in fletes_data:
                    g_ctg = rec.get('g_ctg')
                    if not g_ctg:
                        skipped_count += 1
                        continue

                    # Common data processing
                    kilos_netos = rec.get('o_neto', 0) or 0
                    tarifa = rec.get('g_tarflet', 0) or 0
                    try:
                        kilos_netos_float = float(kilos_netos)
                    except (ValueError, TypeError):
                        kilos_netos_float = 0.0
                    try:
                        tarifa_float = float(tarifa)
                    except (ValueError, TypeError):
                        tarifa_float = 0.0
                    
                    importe = round((kilos_netos_float / 1000) * tarifa_float, 2)
                    
                    # Check if flete exists
                    cursor.execute("SELECT id, o_neto FROM fletes WHERE g_ctg = %s", (g_ctg,))
                    existing_flete = cursor.fetchone()

                    if existing_flete:
                        # 3) Comparar si ha cambiado el Neto para un mismo CTG.
                        if existing_flete['o_neto'] != kilos_netos_float:
                            cursor.execute("""
                                UPDATE fletes 
                                SET g_fecha = %s, g_codi = %s, g_cose = %s, o_peso = %s, o_neto = %s, g_tarflet = %s, g_kilomet = %s, g_ctaplade = %s, g_cuilchof = %s, importe = %s, fuente = %s
                                WHERE id = %s
                            """, (
                                rec.get('g_fecha').strftime('%Y-%m-%d') if isinstance(rec.get('g_fecha'), datetime.date) else None,
                                rec.get('g_codi'),
                                rec.get('g_cose'),
                                rec.get('o_peso'),
                                kilos_netos_float,
                                tarifa_float,
                                (rec.get('g_kilometr', 0) or 0) * 2,
                                rec.get('g_ctaplade'),
                                rec.get('g_cuilchof'),
                                importe,
                                'dbf-updated',
                                existing_flete['id']
                            ))
                            updated_count += 1
                        else:
                            skipped_count += 1
                        continue

                    # If it doesn't exist, insert it
                    cursor.execute("""
                        INSERT INTO fletes (g_fecha, g_ctg, g_codi, g_cose, o_peso, o_neto, g_tarflet, g_kilomet, g_ctaplade, g_cuilchof, importe, fuente)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        rec.get('g_fecha').strftime('%Y-%m-%d') if isinstance(rec.get('g_fecha'), datetime.date) else None,
                        g_ctg,
                        rec.get('g_codi'),
                        rec.get('g_cose'),
                        rec.get('o_peso'),
                        kilos_netos_float,
                        tarifa_float,
                        (rec.get('g_kilometr', 0) or 0) * 2,
                        rec.get('g_ctaplade'),
                        rec.get('g_cuilchof'),
                        importe,
                        'dbf'
                    ))
                    added_count += 1
            conn.commit()
            return f"Importación completada. {added_count} registros agregados, {updated_count} actualizados, {skipped_count} omitidos."
        except Exception as e:
            conn.rollback()
            return f"Ocurrió un error durante la importación: {e}"
        finally:
            if conn:
                conn.close()
    except Exception as e:
        return f"Ocurrió un error: {e}"

@app.route('/fletes/importar')
def importar_fletes_route():
    mensaje = importar_fletes_desde_acohis()
    return render_template('placeholder.html', title="Importar Fletes", message=mensaje, back_url=url_for('fletes'))

@app.route('/fletes/update_km', methods=['POST'])
def update_km():
    try:
        flete_id = request.form['id']
        km = request.form['km'] 
        
        conn = get_db()
        if not conn:
            return jsonify({'success': False, 'error': 'No se pudo conectar a la base de datos.'})
        
        try:
            with get_dict_cursor(conn) as cursor:
                cursor.execute("UPDATE fletes SET g_kilomet = %s WHERE id = %s", (km, flete_id))
            conn.commit()
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)})
        finally:
            if conn:
                conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/fletes/nuevo', methods=['GET', 'POST'])
def nuevo_flete():
    conn = get_db()
    if not conn:
        return "<h1>Error: No se pudo conectar a la base de datos.</h1>"

    try:
        with get_dict_cursor(conn) as cursor:
            if request.method == 'POST':
                try:
                    g_fecha = request.form['g_fecha']
                    g_ctg = request.form['g_ctg']
                    g_codi = request.form['g_codi']
                    g_cose = request.form['g_cose']
                    o_peso = float(request.form['o_peso'])
                    o_tara = float(request.form['o_tara'])
                    g_tarflet = float(request.form['g_tarflet'])
                    g_kilomet = int(request.form['g_kilomet'])
                    g_ctaplade = request.form['g_ctaplade']
                    g_cuilchof = request.form['g_cuilchof']
                    categoria = request.form['categoria']

                    if o_peso <= o_tara:
                        return "Error: Los Kilos Brutos deben ser mayores que los Kilos Tara."

                    o_neto = o_peso - o_tara
                    
                    importe = round((o_neto / 1000) * g_tarflet, 2)

                    cursor.execute("""
                        INSERT INTO fletes (g_fecha, g_ctg, g_codi, g_cose, o_peso, o_neto, g_tarflet, g_kilomet, g_ctaplade, g_cuilchof, importe, fuente, categoria)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (g_fecha, g_ctg, g_codi, g_cose, o_peso, o_neto, g_tarflet, g_kilomet, g_ctaplade, g_cuilchof, importe, 'manual', categoria))
                    
                    conn.commit()
                    return redirect(url_for('fletes'))
                except psycopg2.IntegrityError:
                    conn.rollback()
                    return "Error: El CTG ya existe."
                except Exception as e:
                    conn.rollback()
                    return f"Error al guardar el flete: {e}"

            # Para GET, obtener datos para los dropdowns
            cursor.execute("SELECT g_codi, g_desc FROM acogran")
            granos_map = {rec['g_codi']: rec['g_desc'].strip() for rec in cursor.fetchall()}

            cursor.execute("SELECT c_document, c_nombre FROM choferes")
            choferes_map = {rec['c_document'].strip(): rec['c_nombre'].strip() for rec in cursor.fetchall() if rec.get('c_document') and rec.get('c_nombre')}
            
            sorted_choferes = OrderedDict(sorted(choferes_map.items(), key=lambda item: item[1]))

            cursor.execute("SELECT cli_c, s_locali FROM sysmae WHERE s_locali IS NOT NULL AND s_locali != '' ORDER BY s_locali")
            localidades_temp = {rec['s_locali'].strip(): rec['cli_c'].strip() for rec in cursor.fetchall()}
            sorted_localidades = OrderedDict(sorted({v: k for k, v in localidades_temp.items()}.items(), key=lambda item: item[1]))

            today_date = datetime.date.today().strftime('%Y-%m-%d')
                    
            return render_template('nuevo_flete.html', 
                                   granos=granos_map, 
                                   choferes=sorted_choferes, 
                                   localidades=sorted_localidades,
                                   today_date=today_date)
    finally:
        if conn:
            conn.close()

@app.route('/fletes', methods=['GET', 'POST'])
def fletes():
    try:
        fletes_procesados = []
        sorted_choferes_filtrados = OrderedDict()
        filtros_aplicados = {}
        nombre_chofer_seleccionado = None
        totales = {'neto': 0, 'importe': 0, 'viajes': 0, 'km': 0}
        granos_map = {}
        sorted_all_choferes = OrderedDict()
        unique_localidades = OrderedDict()
        categorias = []
        
        conn = get_db()
        if not conn:
            return "<h1>Error: No se pudo conectar a la base de datos.</h1>"

        try:
            with get_dict_cursor(conn) as cursor:
                # --- Mapeo de Granos, Localidades, Choferes ---
                cursor.execute("SELECT g_codi, g_desc FROM acogran")
                granos_map = {rec['g_codi']: rec['g_desc'].strip() for rec in cursor.fetchall()}

                cursor.execute("SELECT cli_c, s_locali FROM sysmae WHERE s_locali IS NOT NULL AND s_locali != ''")
                all_localidades = cursor.fetchall()
                
                localidades_map = {rec['cli_c'].strip(): rec['s_locali'].strip() for rec in all_localidades}

                localidades_temp = {rec['s_locali'].strip(): rec['cli_c'].strip() for rec in all_localidades}
                unique_localidades = OrderedDict(sorted({v: k for k, v in localidades_temp.items()}.items(), key=lambda item: item[1]))


                cursor.execute("SELECT c_document, c_nombre FROM choferes")
                choferes_map = {rec['c_document'].strip(): rec['c_nombre'].strip() for rec in cursor.fetchall() if rec.get('c_document') and rec.get('c_nombre')}

                # --- Obtener Categorías para el filtro ---
                cursor.execute("SELECT DISTINCT categoria FROM fletes WHERE categoria IS NOT NULL AND categoria != ''")
                categorias_db = [row['categoria'] for row in cursor.fetchall()]
                # Añadir las categorías hardcoded y asegurarse de que sean únicas
                categorias = sorted(list(set(categorias_db + ['ROSARIO', 'ARRIMES', 'HARINA - OTROS'])))

                # --- Filtros ---
                if request.method == 'POST':
                    filtros_aplicados['chofer'] = request.form.get('chofer')
                    filtros_aplicados['fecha_desde'] = request.form.get('fecha_desde')
                    filtros_aplicados['fecha_hasta'] = request.form.get('fecha_hasta')
                    filtros_aplicados['categoria'] = request.form.get('categoria')
                else: # GET
                    today = datetime.date.today()
                    first_day_of_month = today.replace(day=1)
                    filtros_aplicados['fecha_desde'] = first_day_of_month.strftime('%Y-%m-%d')
                    filtros_aplicados['fecha_hasta'] = today.strftime('%Y-%m-%d')
                    filtros_aplicados['chofer'] = None
                    filtros_aplicados['categoria'] = None
                
                query = "SELECT * FROM fletes WHERE 1=1"
                params = []

                if filtros_aplicados.get('chofer'):
                    query += " AND g_cuilchof = %s"
                    params.append(filtros_aplicados['chofer'])
                if filtros_aplicados.get('fecha_desde'):
                    query += " AND g_fecha >= %s"
                    params.append(filtros_aplicados['fecha_desde'])
                if filtros_aplicados.get('fecha_hasta'):
                    query += " AND g_fecha <= %s"
                    params.append(filtros_aplicados['fecha_hasta'])
                
                # Añadir filtro de categoría
                categoria_filtro = filtros_aplicados.get('categoria')
                if categoria_filtro:
                    if categoria_filtro == 'ROSARIO':
                        query += " AND (categoria = %s OR g_ctg LIKE %s)"
                        params.append('ROSARIO')
                        params.append('102%')
                    elif categoria_filtro == 'ARRIMES':
                        query += " AND (categoria = %s OR g_ctg LIKE %s)"
                        params.append('ARRIMES')
                        params.append('101%')
                    else:
                        query += " AND categoria = %s"
                        params.append(categoria_filtro)
                
                query += " ORDER BY g_fecha DESC"
                cursor.execute(query, params)
                fletes_db = cursor.fetchall()

                # --- Procesamiento de Fletes ---
                total_neto = 0
                total_importe = 0
                total_km = 0

                for flete in fletes_db:
                    flete_dict = dict(flete)
                    total_neto += flete_dict.get('o_neto', 0) or 0
                    total_importe += flete_dict.get('importe', 0) or 0
                    
                    # 1) Multiplicar kilometros x 2
                    kilometros = flete_dict.get('g_kilomet', 0) or 0
                    kilometros_ida_y_vuelta = kilometros # los km ya están almacenados como ida y vuelta.
                    total_km += kilometros_ida_y_vuelta

                    flete_dict['g_fecha'] = format_date(flete_dict.get('g_fecha'))
                    flete_dict['g_ctg'] = flete_dict.get('g_ctg') or ''
                    
                    # 2) Asignar categoría según CTG
                    if flete_dict['g_ctg'].startswith('102'):
                        flete_dict['categoria'] = 'ROSARIO'
                    elif flete_dict['g_ctg'].startswith('101'):
                        flete_dict['categoria'] = 'ARRIMES'
                    else:
                        flete_dict['categoria'] = flete_dict.get('categoria') or ''

                    flete_dict['g_cose'] = flete_dict.get('g_cose') or ''
                    flete_dict['o_peso'] = format_number(flete_dict.get('o_peso'), decimals=0)
                    flete_dict['o_neto'] = format_number(flete_dict.get('o_neto'), decimals=0)
                    flete_dict['g_tarflet'] = format_number(flete_dict.get('g_tarflet'), is_currency=True, decimals=2)
                    flete_dict['importe'] = format_number(flete_dict.get('importe'), is_currency=True, decimals=2)
                    flete_dict['g_kilomet'] = format_number(kilometros_ida_y_vuelta, decimals=0)
                    
                    flete_dict['grano'] = granos_map.get(flete_dict['g_codi'], flete_dict['g_codi'])
                    flete_dict['localidad'] = localidades_map.get(flete_dict['g_ctaplade'], flete_dict['g_ctaplade'])
                    flete_dict['g_cuilchof_nombre'] = choferes_map.get(flete_dict['g_cuilchof'], flete_dict['g_cuilchof'])
                    
                    fletes_procesados.append(flete_dict)

                totales = {
                    'neto': format_number(total_neto, decimals=0),
                    'importe': format_number(total_importe, is_currency=True, decimals=2),
                    'viajes': len(fletes_procesados),
                    'km': format_number(total_km, decimals=0)
                }
                
                if filtros_aplicados.get('chofer'):
                    nombre_chofer_seleccionado = choferes_map.get(filtros_aplicados['chofer'])

                # --- Preparar datos para el template ---
                cuils_con_registros = set()
                cursor.execute("SELECT DISTINCT g_cuilchof FROM fletes WHERE g_cuilchof IS NOT NULL AND g_cuilchof != ''")
                for row in cursor.fetchall():
                    cuils_con_registros.add(row['g_cuilchof'].strip())

                choferes_filtrados = {
                    cuil: nombre for cuil, nombre in choferes_map.items()
                    if cuil in cuils_con_registros
                }
                sorted_choferes_filtrados = OrderedDict(sorted(choferes_filtrados.items(), key=lambda item: item[1]))
                sorted_all_choferes = OrderedDict(sorted(choferes_map.items(), key=lambda item: item[1]))
        finally:
            if conn:
                conn.close()

        return render_template('fletes.html', 
                               fletes=fletes_procesados, 
                               choferes=sorted_choferes_filtrados.items(),
                               filtros_aplicados=filtros_aplicados,
                               nombre_chofer=nombre_chofer_seleccionado,
                               totales=totales,
                               granos=granos_map,
                               all_choferes=sorted_all_choferes,
                               localidades=unique_localidades,
                               categorias=categorias)

    except Exception as e:
        import traceback
        return f"<h1>Ocurrió un error: {e}</h1><pre>{traceback.format_exc()}</pre>"

@app.route('/pdf/<tipo_reporte>')
def generar_pdf(tipo_reporte):
    contrato = request.args.get('contrato')
    if not contrato:
        return "Error: No se especificó un contrato.", 400

    temp_filename = f"c:/Tests/Acopio/temp_{tipo_reporte}_{contrato}.pdf"
    conn = get_db()
    if not conn:
        return "<h1>Error: No se pudo conectar a la base de datos.</h1>"

    try:
        if tipo_reporte == 'cuenta_corriente_granaria':
            title = f'Reporte de Cuenta Corriente Granaria - Contrato {contrato}'
            headers = ['Fecha', 'Comprobante', 'Descripción', 'Entregas', 'Liquidaciones', 'Saldo']
            
            movimientos = []
            with get_dict_cursor(conn) as cursor:
                # Obtener Entregas
                cursor.execute("SELECT g_fecha, g_ctg, g_saldo FROM acocarpo WHERE g_contrato = %s", (contrato,))
                for rec in cursor.fetchall():
                    if isinstance(rec.get('g_fecha'), datetime.date):
                        movimientos.append({
                            'fecha': rec['g_fecha'],
                            'comprobante': rec.get('g_ctg', ''),
                            'descripcion': f"Entrega - CTG: {rec.get('g_ctg', '')}",
                            'entregas': rec.get('g_saldo', 0) or 0,
                            'liquidaciones': 0
                        })
                
                # Obtener Liquidaciones
                cursor.execute("SELECT fec_c, fac_c, fa1_c, peso FROM liqven WHERE contrato = %s", (contrato,))
                for rec in cursor.fetchall():
                    if isinstance(rec.get('fec_c'), datetime.date):
                        fac_c_padded = str(rec.get('fac_c', '')).zfill(8)
                        coe_val = f"{rec.get('fa1_c', '')}-{fac_c_padded}"
                        movimientos.append({
                            'fecha': rec['fec_c'],
                            'comprobante': coe_val,
                            'descripcion': f"Liquidación - COE: {coe_val}",
                            'entregas': 0,
                            'liquidaciones': rec.get('peso', 0) or 0
                        })
            
            movimientos.sort(key=lambda x: x['fecha'])
            
            saldo = 0
            table_data = []
            for mov in movimientos:
                saldo += mov['entregas'] - mov['liquidaciones']
                table_data.append(OrderedDict([
                    ('Fecha', format_date(mov['fecha'])),
                    ('Comprobante', mov['comprobante']),
                    ('Descripción', mov['descripcion']),
                    ('Entregas', format_number(mov['entregas'])),
                    ('Liquidaciones', format_number(mov['liquidaciones'])),
                    ('Saldo', format_number(saldo))
                ]))
            
            if not table_data:
                return f"No se encontraron datos para el contrato {contrato} en el reporte de {tipo_reporte}.", 404

            pdf = PDF()
            pdf.title = title
            pdf.add_page()
            pdf.create_table(table_data, headers)
            pdf.output(temp_filename)

            with open(temp_filename, 'rb') as f:
                pdf_data = f.read()
            
            return Response(pdf_data,
                            mimetype='application/pdf',
                            headers={'Content-Disposition': f'attachment;filename={tipo_reporte}_{contrato}.pdf'})

        elif tipo_reporte == 'entregas':
            table_name = 'acocarpo'
            filter_column = 'g_contrato'
            title = f'Reporte de Entregas - Contrato {contrato}'
            headers = ['FECHA', 'Nro Interno', 'CTG', 'Kilos Netos', 'DESTINO']
        elif tipo_reporte == 'liquidaciones':
            table_name = 'liqven'
            filter_column = 'contrato'
            title = f'Reporte de Liquidaciones - Contrato {contrato}'
            headers = ['Fecha', 'COE', 'Peso', 'Precio', 'N.Grav.', 'IVA', 'Otros', 'Total']
        else:
            return "Error: Tipo de reporte no válido.", 400

        with get_dict_cursor(conn) as cursor:
            cursor.execute(f"SELECT * FROM {table_name} WHERE {filter_column} = %s", (contrato,))
            registros = cursor.fetchall()

        if not registros:
            return f"No se encontraron datos para el contrato {contrato} en el reporte de {tipo_reporte}.", 404

        pdf = PDF()
        pdf.title = title
        pdf.add_page()
        
        table_data = []
        totals_dict = None

        if tipo_reporte == 'entregas':
            entregas_confirmadas_pdf = []
            entregas_no_confirmadas_pdf = []
            total_confirmadas_pdf = 0
            total_no_confirmadas_pdf = 0

            key_map = {'FECHA': 'g_fecha', 'Nro Interno': 'g_roman', 'CTG': 'g_ctg', 'Kilos Netos': 'g_saldo', 'DESTINO': 'g_destino'}

            for registro in registros:
                row_data = OrderedDict()
                for header, db_key in key_map.items():
                    value = registro.get(db_key, '')
                    if 'FECHA' in header.upper():
                        value = format_date(value)
                    elif header == 'Kilos Netos':
                        value = format_number(value)
                    row_data[header] = value

                if registro.get('g_confirm', 'N').strip().upper() == 'S':
                    row_data['confirmed'] = True
                    entregas_confirmadas_pdf.append(row_data)
                    total_confirmadas_pdf += registro.get('g_saldo', 0) or 0
                else:
                    row_data['confirmed'] = False
                    entregas_no_confirmadas_pdf.append(row_data)
                    total_no_confirmadas_pdf += registro.get('g_saldo', 0) or 0
            
            table_data.extend(entregas_no_confirmadas_pdf)
            table_data.extend(entregas_confirmadas_pdf)

            totals_dict = {
                'type': 'entregas',
                'total_confirmadas': format_number(total_confirmadas_pdf),
                'registros_confirmadas': len(entregas_confirmadas_pdf),
                'total_no_confirmadas': format_number(total_no_confirmadas_pdf),
                'registros_no_confirmadas': len(entregas_no_confirmadas_pdf),
                'total_general': format_number(total_confirmadas_pdf + total_no_confirmadas_pdf),
                'registros_general': len(registros)
            }
        
        elif tipo_reporte == 'liquidaciones':
            sumas_pdf = { 'Peso': 0, 'N.Grav.': 0, 'IVA': 0, 'Otros': 0, 'Total': 0 }
            for registro in registros:
                otros_val_num = sum(registro.get(col, 0) or 0 for col in ['otr_gas', 'iva_gas', 'gas_com', 'iva_com', 'gas_var', 'iva_var'])
                sumas_pdf['Peso'] += registro.get('peso', 0) or 0
                sumas_pdf['N.Grav.'] += registro.get('bru_c', 0) or 0
                sumas_pdf['IVA'] += registro.get('iva_c', 0) or 0
                sumas_pdf['Otros'] += otros_val_num
                sumas_pdf['Total'] += registro.get('net_cta', 0) or 0

                fac_c_padded = str(registro.get('fac_c', '')).zfill(8)
                coe_val = f"{registro.get('fa1_c', '')}-{fac_c_padded}"

                row_data = OrderedDict()
                row_data['Fecha'] = format_date(registro.get('fec_c', ''))
                row_data['COE'] = coe_val
                row_data['Peso'] = format_number(registro.get('peso', 0))
                row_data['Precio'] = format_number(registro.get('preope', 0), is_currency=True)
                row_data['N.Grav.'] = format_number(registro.get('bru_c', 0), is_currency=True)
                row_data['IVA'] = format_number(registro.get('iva_c', 0), is_currency=True)
                row_data['Otros'] = format_number(otros_val_num, is_currency=True)
                row_data['Total'] = format_number(registro.get('net_cta', 0), is_currency=True)
                table_data.append(row_data)
            
            totals_dict = {
                'type': 'liquidaciones',
                'sums': {key: format_number(val, is_currency=(key != 'Peso')) for key, val in sumas_pdf.items()}
            }

        pdf.create_table(table_data, headers, totals=totals_dict)
        pdf.output(temp_filename)

        with open(temp_filename, 'rb') as f:
            pdf_data = f.read()
        
        return Response(pdf_data,
                        mimetype='application/pdf',
                        headers={'Content-Disposition': f'attachment;filename={tipo_reporte}_{contrato}.pdf'})

    except Exception as e:
        return f"<h1>Ocurrió un error al generar el PDF: {e}</h1>", 500
    finally:
        if conn:
            conn.close()
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@app.route('/test_choferes')
def test_choferes():
    conn = get_db()
    if not conn:
        return "<h1>Error: No se pudo conectar a la base de datos.</h1>"
    try:
        with get_dict_cursor(conn) as cursor:
            cursor.execute("SELECT * FROM choferes LIMIT 1")
            return str(cursor.fetchone())
    except Exception as e:
        return str(e)
    finally:
        if conn:
            conn.close()

@app.route('/debug-acohis-last10')
def debug_acohis_last10():
    conn = get_db()
    if not conn:
        return "<h1>Error: No se pudo conectar a la base de datos.</h1>"
    try:
        with get_dict_cursor(conn) as cursor:
            cursor.execute("SELECT * FROM acohis ORDER BY g_fecha DESC LIMIT 10")
            records = cursor.fetchall()
            formatted_records = []
            for rec in records:
                formatted_rec = {}
                for field_name, value in rec.items():
                    if isinstance(value, datetime.date):
                        formatted_rec[field_name] = value.strftime('%Y-%m-%d')
                    else:
                        formatted_rec[field_name] = value
                formatted_records.append(formatted_rec)
            return render_template('debug.html', records=formatted_records, dbf_name="acohis")
    except Exception as e:
        return f"<h1>Ocurrió un error al leer el archivo: {e}</h1>"
    finally:
        if conn:
            conn.close()

@app.route('/fletes/<int:flete_id>')
def get_flete(flete_id):
    conn = get_db()
    if not conn:
        return jsonify({'error': 'Flete not found'}), 404
    try:
        with get_dict_cursor(conn) as cursor:
            cursor.execute('SELECT * FROM fletes WHERE id = %s', (flete_id,))
            flete = cursor.fetchone()
            if flete is None:
                return jsonify({'error': 'Flete not found'}), 404
            
            # Convert row object to a dictionary
            flete_dict = dict(flete)
            if isinstance(flete_dict.get('g_fecha'), datetime.date):
                flete_dict['g_fecha'] = flete_dict['g_fecha'].strftime('%Y-%m-%d')
            return jsonify(flete_dict)
    finally:
        if conn:
            conn.close()

@app.route('/fletes/edit/<int:flete_id>', methods=['POST'])
def edit_flete(flete_id):
    conn = get_db()
    if not conn:
        return "<h1>Error: No se pudo conectar a la base de datos.</h1>"
    try:
        with get_dict_cursor(conn) as cursor:
            form_data = request.form
            
            g_fecha = form_data.get('g_fecha')
            g_ctg = form_data.get('g_ctg')
            g_codi = form_data.get('g_codi')
            g_cose = form_data.get('g_cose', '') # Optional
            o_peso_str = form_data.get('o_peso')
            o_tara_str = form_data.get('o_tara')
            g_tarflet_str = form_data.get('g_tarflet')
            g_kilomet_str = form_data.get('g_kilomet')
            g_ctaplade = form_data.get('g_ctaplade', '') # Optional
            g_cuilchof = form_data.get('g_cuilchof')
            categoria = form_data.get('categoria', '') # Optional

            required_fields_for_check = {
                'g_fecha': g_fecha,
                'g_ctg': g_ctg,
                'g_codi': g_codi,
                'o_peso': o_peso_str,
                'o_tara': o_tara_str,
                'g_tarflet': g_tarflet_str,
                'g_kilomet': g_kilomet_str,
                'g_cuilchof': g_cuilchof
            }
            
            missing_fields = [key for key, value in required_fields_for_check.items() if value is None]
            if missing_fields:
                return f"Error: Faltan los siguientes campos en el formulario: {', '.join(missing_fields)}", 400

            try:
                o_peso = float(o_peso_str)
                o_tara = float(o_tara_str)
                g_tarflet = float(g_tarflet_str)
                g_kilomet = int(g_kilomet_str)
            except (ValueError, TypeError):
                return "Error: Kilos, Tara, Tarifa y Kilómetros deben ser números válidos.", 400


            if o_peso <= o_tara:
                return "Error: Los Kilos Brutos deben ser mayores que los Kilos Tara."

            o_neto = o_peso - o_tara
            
            importe = round((o_neto / 1000) * g_tarflet, 2)

            cursor.execute("""
                UPDATE fletes 
                SET g_fecha = %s, g_ctg = %s, g_codi = %s, g_cose = %s, o_peso = %s, o_neto = %s, g_tarflet = %s, g_kilomet = %s, g_ctaplade = %s, g_cuilchof = %s, importe = %s, categoria = %s
                WHERE id = %s
            """, (g_fecha, g_ctg, g_codi, g_cose, o_peso, o_neto, g_tarflet, g_kilomet, g_ctaplade, g_cuilchof, importe, categoria, flete_id))
            
            conn.commit()
            return redirect(url_for('fletes'))
    except psycopg2.IntegrityError:
        conn.rollback()
        return "Error: El CTG ya existe."
    except Exception as e:
        conn.rollback()
        import traceback
        return f"Error al editar el flete: {e}<br><pre>{traceback.format_exc()}</pre>", 500
    finally:
        if conn:
            conn.close()

@app.route('/fletes/delete/<int:flete_id>', methods=['POST'])
def delete_flete(flete_id):
    conn = get_db()
    if not conn:
        return "<h1>Error: No se pudo conectar a la base de datos.</h1>"
    try:
        with get_dict_cursor(conn) as cursor:
            cursor.execute("DELETE FROM fletes WHERE id = %s", (flete_id,))
        conn.commit()
        return redirect(url_for('fletes'))
    except Exception as e:
        conn.rollback()
        return f"Error al eliminar el flete: {e}"
    finally:
        if conn:
            conn.close()

@app.route('/combustible', methods=['GET', 'POST'])
def combustible():
    conn = get_db()
    if not conn:
        return "<h1>Error: No se pudo conectar a la base de datos.</h1>"

    try:
        with get_dict_cursor(conn) as cursor:
            if request.method == 'POST':
                tipo_operacion = request.form.get('tipo_operacion')
                proveedor_id = request.form.get('proveedor_id') if request.form.get('proveedor_id') else None
                chofer_documento = request.form.get('chofer_documento')
                nro_comprobante = request.form.get('nro_comprobante')
                fecha_movimiento_str = request.form.get('fecha_movimiento') # Get the manual date
                fecha_movimiento = datetime.datetime.strptime(fecha_movimiento_str, '%Y-%m-%d') if fecha_movimiento_str else datetime.datetime.now()

                # Asegurarse que el precio unitario sea None si está vacío
                def clean_price(price_str):
                    if price_str is None or price_str.strip() == '':
                        return None
                    try:
                        return Decimal(price_str)
                    except:
                        return None

                if tipo_operacion == 'Canje':
                    producto_sale_id = request.form.get('producto_sale_id')
                    cantidad_sale = Decimal(request.form.get('cantidad_sale', 0))
                    producto_entra_id = request.form.get('producto_entra_id')
                    cantidad_entra = Decimal(request.form.get('cantidad_entra', 0))
                    precio_unitario = clean_price(request.form.get('precio_unitario_canje'))
                    
                    # Insertar salida
                    cursor.execute("""
                        INSERT INTO combustible_movimientos (fecha, proveedor_id, chofer_documento, tipo_operacion, nro_comprobante, producto_id, cantidad, precio_unitario)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                    """, (fecha_movimiento, proveedor_id, chofer_documento, 'Canje - Salida', nro_comprobante, producto_sale_id, -abs(cantidad_sale), None))
                    id_salida = cursor.fetchone()[0]

                    # Insertar entrada
                    cursor.execute("""
                        INSERT INTO combustible_movimientos (fecha, proveedor_id, chofer_documento, tipo_operacion, nro_comprobante, producto_id, cantidad, precio_unitario, id_transaccion_canje)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (fecha_movimiento, proveedor_id, chofer_documento, 'Canje - Entrada', nro_comprobante, producto_entra_id, abs(cantidad_entra), precio_unitario, id_salida))
                    
                else: # Compra o Retiro
                    producto_id = request.form.get('producto_id')
                    cantidad = Decimal(request.form.get('cantidad', 0))
                    precio_unitario = clean_price(request.form.get('precio_unitario'))

                    if tipo_operacion == 'Retiro':
                        cantidad = -abs(cantidad)

                    cursor.execute("""
                        INSERT INTO combustible_movimientos (fecha, proveedor_id, chofer_documento, tipo_operacion, nro_comprobante, producto_id, cantidad, precio_unitario)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (fecha_movimiento, proveedor_id, chofer_documento, tipo_operacion, nro_comprobante, producto_id, cantidad, precio_unitario))

                conn.commit()
                return redirect(url_for('combustible'))

            # --- Lógica para GET ---
            cursor.execute("SELECT cli_c, s_apelli FROM sysmae WHERE s_zonacu = 'PP' ORDER BY s_apelli")
            proveedores = cursor.fetchall()
            cursor.execute("SELECT id, nombre FROM combustible_productos ORDER BY nombre")
            productos = cursor.fetchall()
            cursor.execute("SELECT c_document, c_nombre FROM choferes ORDER BY c_nombre")
            choferes = cursor.fetchall()

            query = """
                SELECT 
                    m.id, m.fecha, m.tipo_operacion, m.nro_comprobante, m.cantidad, m.precio_unitario,
                    p.s_apelli as proveedor_nombre,
                    c.c_nombre as chofer_nombre,
                    pr.nombre as producto_nombre
                FROM combustible_movimientos m
                LEFT JOIN sysmae p ON m.proveedor_id = p.cli_c
                LEFT JOIN choferes c ON m.chofer_documento = c.c_document
                LEFT JOIN combustible_productos pr ON m.producto_id = pr.id
                WHERE 1=1
            """
            params = []
            if request.args.get('filtro_proveedor'):
                query += " AND m.proveedor_id = %s"
                params.append(request.args.get('filtro_proveedor'))
            if request.args.get('filtro_chofer'):
                query += " AND m.chofer_documento = %s"
                params.append(request.args.get('filtro_chofer'))
            if request.args.get('filtro_producto'):
                query += " AND m.producto_id = %s"
                params.append(request.args.get('filtro_producto'))
            if request.args.get('filtro_fecha_inicio'):
                query += " AND m.fecha >= %s"
                params.append(request.args.get('filtro_fecha_inicio'))
            if request.args.get('filtro_fecha_fin'):
                query += " AND m.fecha <= %s"
                params.append(request.args.get('filtro_fecha_fin'))

            query += " ORDER BY m.fecha DESC"
            cursor.execute(query, params)
            movimientos = cursor.fetchall()

            cursor.execute("""
                SELECT 
                    p.s_apelli as proveedor, 
                    pr.nombre as producto, 
                    SUM(m.cantidad) as stock
                FROM combustible_movimientos m
                LEFT JOIN sysmae p ON m.proveedor_id = p.cli_c
                LEFT JOIN combustible_productos pr ON m.producto_id = pr.id
                GROUP BY p.s_apelli, pr.nombre
                HAVING SUM(m.cantidad) != 0
                ORDER BY p.s_apelli, pr.nombre
            """)
            stock = cursor.fetchall()

            today_date = datetime.date.today().strftime('%Y-%m-%d') # Get today's date for the template

            return render_template('combustible.html', 
                                   movimientos=movimientos,
                                   proveedores=proveedores,
                                   productos=productos,
                                   choferes=choferes,
                                   stock=stock,
                                   today_date=today_date) # Pass today_date to the template
    except Exception as e:
        conn.rollback()
        import traceback
        return f"<h1>Ocurrió un error en la sección de Combustible: {e}</h1><pre>{traceback.format_exc()}</pre>"
    finally:
        if conn:
            conn.close()

@app.route('/add_combustible_producto', methods=['POST'])
def add_combustible_producto():
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'No se pudo conectar a la base de datos.'})
    try:
        data = request.json
        nombre = data.get('nombre')
        if not nombre:
            return jsonify({'success': False, 'error': 'El nombre es requerido.'})

        with get_dict_cursor(conn) as cursor:
            cursor.execute("INSERT INTO combustible_productos (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING RETURNING id, nombre", (nombre,))
            new_producto = cursor.fetchone()
            conn.commit()
            if not new_producto:
                cursor.execute("SELECT id, nombre FROM combustible_productos WHERE nombre = %s", (nombre,))
                new_producto = cursor.fetchone()

        return jsonify({'success': True, 'producto': dict(new_producto)})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if conn:
            conn.close()

@app.route('/export_compras_pdf')

def export_compras_pdf():

    conn = get_db()

    if not conn:

        return "<h1>Error: No se pudo conectar a la base de datos.</h1>", 500



    try:

        with get_dict_cursor(conn) as cursor:

            # --- Obtener valores para mapeo ---

            cursor.execute("SELECT g_codi, g_desc FROM acogran")

            granos = {rec['g_codi']: rec['g_desc'].strip() for rec in cursor.fetchall()}

            

            cursor.execute("SELECT cli_c, s_apelli FROM sysmae")

            vendedores = {rec['cli_c']: rec['s_apelli'].strip() for rec in cursor.fetchall()}



            cursor.execute("SELECT cli_c, s_locali FROM sysmae")

            origenes = {rec['cli_c']: rec['s_locali'].strip() for rec in cursor.fetchall()}



            # --- Procesar filtros ---

            filtros = request.args

            query = "SELECT * FROM acohis WHERE g_ctl = 'I'"

            params = []



            if filtros.get('fecha_desde'):

                query += " AND g_fecha >= %s"

                params.append(filtros['fecha_desde'])

            if filtros.get('fecha_hasta'):
                query += " AND g_fecha <= %s"
                params.append(filtros['fecha_hasta'])
            if filtros.get('vendedor'):
                query += " AND cli_c = %s"
                params.append(filtros['vendedor'])
            if filtros.get('grano'):

                query += " AND g_codi = %s"

                params.append(filtros['grano'])

            if filtros.get('cosecha'):

                query += " AND g_cose = %s"

                params.append(filtros['cosecha'])

            if filtros.get('origen'):

                query += " AND g_ctaplade = %s"

                params.append(filtros['origen'])

            

            query += " ORDER BY g_fecha DESC"

            cursor.execute(query, params)

            compras_data = cursor.fetchall()



            if not compras_data:

                return "No se encontraron registros para generar el PDF.", 404



            # --- Generar PDF ---

            pdf = PDF(orientation='L', unit='mm', format='A4')

            pdf.title = 'Reporte de Compras'

            pdf.add_page()

            

            headers = ['Fecha', 'CTG', 'Vendedor', 'Grano', 'Cosecha', 'Origen', 'K. Brutos', 'Mermas', 'K. Netos']

            

            table_data = []

            for compra in compras_data:

                kilos_brutos = compra.get('o_peso', 0) or 0

                kilos_netos = compra.get('o_neto', 0) or 0

                mermas = kilos_brutos - kilos_netos



                row = OrderedDict()

                row['Fecha'] = format_date(compra.get('g_fecha'))

                row['CTG'] = compra.get('g_ctg', '')

                row['Vendedor'] = vendedores.get(compra.get('cli_c'), '')

                row['Grano'] = granos.get(compra.get('g_codi'), '')

                row['Cosecha'] = compra.get('g_cose', '')

                row['Origen'] = origenes.get(compra.get('g_ctaplade'), '')

                row['K. Brutos'] = format_number(kilos_brutos, decimals=2)

                row['Mermas'] = format_number(mermas, decimals=2)

                row['K. Netos'] = format_number(kilos_netos, decimals=2)

                table_data.append(row)



            pdf.create_table(table_data, headers=headers)

            

            # Devolver el PDF como respuesta

            pdf_output = pdf.output(dest='S').encode('latin-1')

            return Response(pdf_output,

                            mimetype='application/pdf',

                            headers={'Content-Disposition': 'attachment;filename=reporte_compras.pdf'})



    except Exception as e:

        import traceback

        return f"<h1>Ocurrió un error al generar el PDF: {e}</h1><pre>{traceback.format_exc()}</pre>", 500

    finally:

        if conn:

            conn.close()





@app.route('/agenda', methods=['GET', 'POST'])
def agenda():
    conn = get_db()
    if not conn:
        return "<h1>Error: No se pudo conectar a la base de datos.</h1>"

    try:
        with get_dict_cursor(conn) as cursor:
            today = datetime.date.today() # Define today here

            if request.method == 'POST':
                action = request.form.get('action')

                if action == 'add':
                    descripcion = request.form.get('descripcion')
                    fecha_vencimiento_str = request.form.get('fecha_vencimiento')
                    link = request.form.get('link')
                    frecuencia = request.form.get('frecuencia')
                    
                    fecha_vencimiento = datetime.datetime.strptime(fecha_vencimiento_str, '%Y-%m-%d').date()

                    if fecha_vencimiento < today:
                        # Aquí podrías pasar un mensaje de error a la plantilla
                        print("Error: No se puede agendar una tarea con fecha vencida.")
                    else:
                        cursor.execute(
                            """INSERT INTO agenda (descripcion, fecha_vencimiento, link, frecuencia, completada)
                               VALUES (%s, %s, %s, %s, %s)""",
                            (descripcion, fecha_vencimiento, link, frecuencia, False)
                        )
                        conn.commit()

                elif action == 'complete':
                    tarea_id = request.form.get('tarea_id')
                    cursor.execute("SELECT * FROM agenda WHERE id = %s", (tarea_id,))
                    tarea = cursor.fetchone()

                    if tarea:
                        # Marcar la tarea actual como completada
                        cursor.execute("UPDATE agenda SET completada = TRUE WHERE id = %s", (tarea_id,))

                        # Si es recurrente, crear la nueva tarea
                        if tarea['frecuencia'] != 'unica':
                            nueva_fecha = None
                            if tarea['frecuencia'] == 'diaria':
                                nueva_fecha = tarea['fecha_vencimiento'] + relativedelta(days=1)
                            elif tarea['frecuencia'] == 'semanal':
                                nueva_fecha = tarea['fecha_vencimiento'] + relativedelta(weeks=1)
                            elif tarea['frecuencia'] == 'mensual':
                                nueva_fecha = tarea['fecha_vencimiento'] + relativedelta(months=1)
                            elif tarea['frecuencia'] == 'anual':
                                nueva_fecha = tarea['fecha_vencimiento'] + relativedelta(years=1)
                            
                            # Si la nueva fecha calculada ya pasó, la movemos a hoy.
                            if nueva_fecha and nueva_fecha < today:
                                nueva_fecha = today

                            if nueva_fecha:
                                cursor.execute(
                                    """INSERT INTO agenda (descripcion, fecha_vencimiento, link, frecuencia, completada)
                                       VALUES (%s, %s, %s, %s, %s)""",
                                    (tarea['descripcion'], nueva_fecha, tarea['link'], tarea['frecuencia'], False)
                                )
                        conn.commit()
                
                elif action == 'delete':
                    tarea_id = request.form.get('tarea_id')
                    cursor.execute("DELETE FROM agenda WHERE id = %s", (tarea_id,))
                    conn.commit()

                elif action == 'add_password':
                    titulo = request.form.get('titulo')
                    descripcion = request.form.get('descripcion')
                    link = request.form.get('link')
                    usuario = request.form.get('usuario')
                    contrasena = request.form.get('contrasena')
                    vencimiento_str = request.form.get('vencimiento')
                    vencimiento = None
                    if vencimiento_str:
                        vencimiento = datetime.datetime.strptime(vencimiento_str, '%Y-%m-%d').date()
                    
                    cursor.execute(
                        """INSERT INTO passwords (titulo, descripcion, link, usuario, contrasena, vencimiento)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (titulo, descripcion, link, usuario, contrasena, vencimiento)
                    )
                    conn.commit()

                elif action == 'delete_password':
                    password_id = request.form.get('password_id')
                    cursor.execute("DELETE FROM passwords WHERE id = %s", (password_id,))
                    conn.commit()
                    return redirect(url_for('agenda'))
            
            cursor.execute("SELECT * FROM agenda WHERE completada = FALSE ORDER BY fecha_vencimiento ASC")
            tareas = cursor.fetchall()
            
            cursor.execute("SELECT * FROM passwords ORDER BY titulo ASC")
            passwords = cursor.fetchall()

            return render_template('agenda.html', tareas=tareas, passwords=passwords, today_date=today)

    except Exception as e:
        import traceback
        return f"<h1>Ocurrió un error en la Agenda: {e}</h1><pre>{traceback.format_exc()}</pre>"
    finally:
        if conn:
            conn.close()

















@app.route('/agenda/<int:tarea_id>')
def get_tarea(tarea_id):
    conn = get_db()
    if not conn:
        return jsonify({'error': 'No se pudo conectar a la base de datos.'}), 500
    try:
        with get_dict_cursor(conn) as cursor:
            cursor.execute('SELECT id, descripcion, fecha_vencimiento, link, frecuencia FROM agenda WHERE id = %s', (tarea_id,))
            tarea = cursor.fetchone()
            if tarea is None:
                return jsonify({'error': 'Tarea no encontrada.'}), 404
            
            tarea_dict = dict(tarea)
            if isinstance(tarea_dict.get('fecha_vencimiento'), datetime.date):
                tarea_dict['fecha_vencimiento'] = tarea_dict['fecha_vencimiento'].strftime('%Y-%m-%d')
            return jsonify(tarea_dict)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/agenda/edit/<int:tarea_id>', methods=['POST'])
def edit_tarea(tarea_id):
    conn = get_db()
    if not conn:
        return "<h1>Error: No se pudo conectar a la base de datos.</h1>", 500
    try:
        with get_dict_cursor(conn) as cursor:
            descripcion = request.form.get('descripcion')
            fecha_vencimiento_str = request.form.get('fecha_vencimiento')
            link = request.form.get('link')
            frecuencia = request.form.get('frecuencia')
            
            if not descripcion or not fecha_vencimiento_str or not frecuencia:
                return "Error: Faltan campos obligatorios.", 400
            
            fecha_vencimiento = datetime.datetime.strptime(fecha_vencimiento_str, '%Y-%m-%d').date()
            
            cursor.execute("""
                UPDATE agenda 
                SET descripcion = %s, fecha_vencimiento = %s, link = %s, frecuencia = %s
                WHERE id = %s
            """, (descripcion, fecha_vencimiento, link, frecuencia, tarea_id))
            
            conn.commit()
            return redirect(url_for('agenda'))
    except Exception as e:
        conn.rollback()
        import traceback
        return f"Error al editar la tarea: {e}<br><pre>{traceback.format_exc()}</pre>", 500
    finally:
        if conn:
            conn.close()

@app.route('/combustible/get/<int:movement_id>', methods=['GET'])
def get_combustible_movement(movement_id):
    conn = get_db()
    if not conn:
        return jsonify({'error': 'No se pudo conectar a la base de datos.'}), 500
    try:
        with get_dict_cursor(conn) as cursor:
            cursor.execute('SELECT * FROM combustible_movimientos WHERE id = %s', (movement_id,))
            movement = cursor.fetchone()
            if movement is None:
                return jsonify({'error': 'Movimiento no encontrado.'}), 404
            
            movement_dict = dict(movement)
            # Convert datetime object to string for JSON serialization
            if isinstance(movement_dict.get('fecha'), datetime.datetime):
                movement_dict['fecha'] = movement_dict['fecha'].isoformat()
            
            # Convert Decimal to float for JSON serialization
            if isinstance(movement_dict.get('cantidad'), Decimal):
                movement_dict['cantidad'] = float(movement_dict['cantidad'])
            if isinstance(movement_dict.get('precio_unitario'), Decimal):
                movement_dict['precio_unitario'] = float(movement_dict['precio_unitario'])

            return jsonify(movement_dict)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/combustible/edit/<int:movement_id>', methods=['POST'])
def edit_combustible_movement(movement_id):
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'No se pudo conectar a la base de datos.'}), 500
    try:
        with get_dict_cursor(conn) as cursor:
            fecha_movimiento_str = request.form.get('fecha_movimiento')
            fecha_movimiento = datetime.datetime.strptime(fecha_movimiento_str, '%Y-%m-%d') if fecha_movimiento_str else None
            proveedor_id = request.form.get('proveedor_id') if request.form.get('proveedor_id') else None
            chofer_documento = request.form.get('chofer_documento')
            nro_comprobante = request.form.get('nro_comprobante')
            producto_id = request.form.get('producto_id')
            cantidad = Decimal(request.form.get('cantidad', 0))
            precio_unitario_str = request.form.get('precio_unitario')

            def clean_price(price_str):
                if price_str is None or price_str.strip() == '':
                    return None
                try:
                    return Decimal(price_str)
                except:
                    return None
            precio_unitario = clean_price(precio_unitario_str)

            cursor.execute("""
                UPDATE combustible_movimientos
                SET fecha = %s, proveedor_id = %s, chofer_documento = %s, nro_comprobante = %s,
                    producto_id = %s, cantidad = %s, precio_unitario = %s
                WHERE id = %s
            """, (fecha_movimiento, proveedor_id, chofer_documento, nro_comprobante,
                  producto_id, cantidad, precio_unitario, movement_id))
            conn.commit()
            return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/combustible/delete/<int:movement_id>', methods=['POST'])
def delete_combustible_movement(movement_id):
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'No se pudo conectar a la base de datos.'}), 500
    try:
        with get_dict_cursor(conn) as cursor:
            # Check if this movement is part of a 'Canje' transaction
            cursor.execute("SELECT id_transaccion_canje, tipo_operacion FROM combustible_movimientos WHERE id = %s", (movement_id,))
            movement_info = cursor.fetchone()

            if movement_info and movement_info['tipo_operacion'].startswith('Canje'):
                if movement_info['tipo_operacion'] == 'Canje - Salida':
                    # If it's a 'Canje - Salida', delete the corresponding 'Canje - Entrada'
                    cursor.execute("DELETE FROM combustible_movimientos WHERE id_transaccion_canje = %s", (movement_id,))
                elif movement_info['tipo_operacion'] == 'Canje - Entrada':
                    # If it's a 'Canje - Entrada', find the 'Canje - Salida' and delete it too
                    cursor.execute("DELETE FROM combustible_movimientos WHERE id = %s", (movement_info['id_transaccion_canje'],))
            
            cursor.execute("DELETE FROM combustible_movimientos WHERE id = %s", (movement_id,))
            conn.commit()
            return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':





    app.run(host='0.0.0.0', debug=True)
