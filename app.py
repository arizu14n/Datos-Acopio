# app.py

from flask import Flask, render_template, request, Response, redirect, url_for, jsonify
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
import sqlite3

# --- CONFIGURACIÓN DE LOCALIZACIÓN PARA FORMATO DE NÚMEROS ---
try:
    locale.setlocale(locale.LC_ALL, 'es_AR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'Spanish_Argentina.1252')
    except locale.Error:
        print("Advertencia: No se pudo establecer la localización a es_AR. Los formatos de número pueden ser incorrectos.")

app = Flask(__name__)

# --- CONFIGURACIÓN DE LA BASE DE DATOS SQLITE ---
DATABASE = 'c:/Tests/Acopio/fletes.db'

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    with db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS fletes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                g_fecha TEXT NOT NULL,
                g_ctg TEXT UNIQUE NOT NULL,
                g_codi TEXT,
                g_cose TEXT,
                o_peso REAL,
                o_neto REAL,
                g_tarflet REAL,
                g_kilomet REAL,
                g_ctaplade TEXT,
                g_cuilchof TEXT,
                importe REAL,
                fuente TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS cupos_solicitados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contrato TEXT NOT NULL,
                grano TEXT NOT NULL,
                cosecha TEXT NOT NULL,
                cantidad REAL NOT NULL,
                fecha_solicitud TEXT NOT NULL,
                nombre_persona TEXT NOT NULL,
                codigo_cupo TEXT,
                flete_id INTEGER,
                FOREIGN KEY (flete_id) REFERENCES fletes (id)
            )
        """)
    print("Base de datos inicializada.")

@app.cli.command('init-db')
def init_db_command():
    """Crea la base de datos."""
    init_db()

# --- CONFIGURACIÓN DE RUTAS ---
RUTA_ACOCARPO_DBF = "C:\\acocta5\\acocarpo.dbf"
RUTA_LIQVEN_DBF = "C:\\acocta5\\liqven.dbf"
RUTA_ACOGRAN_DBF = "C:\\acocta5\\acogran.dbf"
RUTA_ACOGRAST_DBF = "C:\\acocta5\\acograst.dbf"
RUTA_CONTRAT_DBF = "C:\\acocta5\\contrat.dbf"
RUTA_ACOHIS_DBF = "C:\\acocta5\\acohis.dbf"
RUTA_SYSMAE_DBF = "C:\\acocta5\\sysmae.dbf"
RUTA_CHOFERES_DBF = "C:\\acocta5\\choferes.dbf"
RUTA_CCBCTA_DBF = "C:\\acocta5\\ccbcta.dbf"

def format_date(date_obj):
    if date_obj is None:
        return ""
    if isinstance(date_obj, datetime.date):
        return date_obj.strftime('%d/%m/%Y')
    return date_obj

def get_grano_description(grano_code):
    try:
        with DBF(RUTA_ACOGRAN_DBF, encoding='iso-8859-1') as tabla_acogran:
            for rec in tabla_acogran:
                if rec.get('G_CODI') == grano_code:
                    return rec.get('G_DESC', grano_code) # Return description or code if not found
    except FileNotFoundError:
        print(f"Advertencia: No se encontró el archivo DBF: {RUTA_ACOGRAN_DBF}")
    except Exception as e:
        print(f"Error al leer {RUTA_ACOGRAN_DBF}: {e}")
    return grano_code # Return code if any error occurs

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
        db = get_db()
        with db:
            cursor = db.cursor()
            query = "SELECT SUM(o_neto) as total_neto, SUM(importe) as total_importe, COUNT(*) as total_viajes, SUM(g_kilomet) as total_km FROM fletes WHERE g_fecha >= ? AND g_fecha <= ?"
            cursor.execute(query, (filtros_aplicados['fecha_desde'], filtros_aplicados['fecha_hasta']))
            fletes_result = cursor.fetchone()
            if fletes_result:
                fletes_data = {
                    'toneladas_transportadas': (fletes_result['total_neto'] or 0) / 1000,
                    'monto_facturado': fletes_result['total_importe'] or 0,
                    'cantidad_viajes': fletes_result['total_viajes'] or 0,
                    'kilometros_recorridos': fletes_result['total_km'] or 0
                }

        # --- Lógica para Panel de Ventas ---
        ventas_por_grano = {}
        total_liquidado_kilos = 0
        total_liquidado_monto = 0

        # Toneladas Entregadas (acocarpo.dbf)
        with DBF(RUTA_ACOCARPO_DBF, encoding='iso-8859-1') as tabla_acocarpo:
            for rec in tabla_acocarpo:
                fecha_entrega = rec.get('G_FECHA')
                if isinstance(fecha_entrega, datetime.date) and fecha_desde_dt <= fecha_entrega <= fecha_hasta_dt:
                    grano_code = rec.get('G_CODI')
                    if not grano_code: continue
                    grano_desc = get_grano_description(grano_code)
                    kilos = rec.get('G_SALDO', 0) or 0
                    if grano_desc not in ventas_por_grano:
                        ventas_por_grano[grano_desc] = {'toneladas_entregadas': 0}
                    ventas_por_grano[grano_desc]['toneladas_entregadas'] += kilos

        # Toneladas y Monto Liquidado (liqven.dbf) - Total en el período
        with DBF(RUTA_LIQVEN_DBF, encoding='iso-8859-1') as tabla_liqven:
            for rec in tabla_liqven:
                fecha_liq = rec.get('FEC_C')
                if isinstance(fecha_liq, datetime.date) and fecha_desde_dt <= fecha_liq <= fecha_hasta_dt:
                    total_liquidado_kilos += rec.get('PESO', 0) or 0
                    total_liquidado_monto += rec.get('NET_CTA', 0) or 0
        
        total_liquidado_toneladas = total_liquidado_kilos / 1000

        # Combinar datos para la tabla
        ventas_data = []
        for grano, data in sorted(ventas_por_grano.items()):
            ventas_data.append({
                'grano': grano,
                'toneladas_entregadas': data['toneladas_entregadas'] / 1000
            })

        # --- Lógica para Tabla de Stock y Pendiente ---
        stock_granos_cosecha = get_stock_granos_por_cosecha()
        _, totales_por_grano_cosecha_stock = get_contratos_pendientes()

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
                    porcentaje_afectado = (pendiente / stock) * 100 if stock > 0 else 100

                    stock_data.append({
                        'grano': grano,
                        'cosecha': cosecha,
                        'stock': stock / 1000,
                        'pendiente': pendiente / 1000,
                        'porcentaje_afectado': porcentaje_afectado
                    })

        # --- Lógica para Panel de Cobranzas ---
        cobranzas_data = None
        vencimientos = 0
        cobrado = 0
        try:
            with DBF(RUTA_CCBCTA_DBF, encoding='iso-8859-1') as tabla_ccbcta:
                for rec in tabla_ccbcta:
                    fecha_vto = rec.get('VTO_F')
                    if isinstance(fecha_vto, datetime.date) and fecha_desde_dt <= fecha_vto <= fecha_hasta_dt:
                        tip_f = rec.get('TIP_F', '').strip().upper()
                        imp_f = rec.get('IMP_F', 0) or 0
                        
                        if tip_f in ('LF', 'LP'):
                            vencimientos += imp_f
                        elif tip_f in ('RI', 'SI', 'SG', 'SB'):
                            cobrado += imp_f
            
            cobranzas_data = {
                'vencimientos': vencimientos,
                'cobrado': cobrado,
                'saldo': vencimientos - cobrado
            }
        except FileNotFoundError:
            print(f"Advertencia: No se encontró el archivo DBF: {RUTA_CCBCTA_DBF}")
            cobranzas_data = {'vencimientos': 0, 'cobrado': 0, 'saldo': 0} # Initialize with zeros if file not found
        except Exception as e:
            print(f"Error al leer {RUTA_CCBCTA_DBF}: {e}")
            cobranzas_data = {'vencimientos': 0, 'cobrado': 0, 'saldo': 0} # Initialize with zeros on error


        return render_template('dashboard.html',
                               filtros_aplicados=filtros_aplicados,
                               fletes_data=fletes_data,
                               ventas_data=ventas_data,
                               total_liquidado_toneladas=total_liquidado_toneladas,
                               total_liquidado_monto=total_liquidado_monto,
                               stock_data=stock_data,
                               cobranzas_data=cobranzas_data)
    except Exception as e:
        # For debugging purposes, returning the error to the page can be helpful
        import traceback
        return f"<h1>Ocurrió un error en el Dashboard: {e}</h1><pre>{traceback.format_exc()}</pre>"

def get_stock_granos_por_cosecha():
    stock_granos = {}
    try:
        with DBF(RUTA_ACOGRAST_DBF, encoding='iso-8859-1') as tabla_acograst:
            for rec in tabla_acograst:
                grano_code = rec.get('G_CODI')
                cosecha = rec.get('G_COSE')
                stock = rec.get('G_STOK', 0)
                if grano_code and cosecha:
                    grano_desc = get_grano_description(grano_code)
                    stock_granos[(grano_desc, cosecha)] = stock
    except FileNotFoundError:
        print(f"Advertencia: No se encontró el archivo DBF: {RUTA_ACOGRAST_DBF}")
    except Exception as e:
        print(f"Error al leer {RUTA_ACOGRAST_DBF}: {e}")
    return stock_granos

def get_contratos_pendientes(min_harvest_year=None):
    contratos_pendientes = []
    totales_por_grano_cosecha = {}

    # Pre-calcular la suma de 'Peso' desde liqven.dbf por contrato
    liquidaciones_por_contrato = {}
    try:
        with DBF(RUTA_LIQVEN_DBF, encoding='iso-8859-1') as tabla_liqven:
            for rec in tabla_liqven:
                contrato_liq = rec.get('CONTRATO')
                # Asegurarse de que el contrato es un string y quitar espacios
                if contrato_liq and isinstance(contrato_liq, str):
                    contrato_liq = contrato_liq.strip()

                peso_liq = float(rec.get('PESO', 0) or 0)
                if contrato_liq:
                    liquidaciones_por_contrato[contrato_liq] = liquidaciones_por_contrato.get(contrato_liq, 0) + peso_liq
    except FileNotFoundError:
        print(f"Advertencia: No se encontró el archivo DBF: {RUTA_LIQVEN_DBF}")
    except Exception as e:
        print(f"Error al leer {RUTA_LIQVEN_DBF}: {e}")

    try:
        with DBF(RUTA_CONTRAT_DBF, encoding='iso-8859-1') as tabla_contrat:
            for i, rec in enumerate(tabla_contrat):
                kiloped = 0.0
                entrega = 0.0
                liquiya = 0.0

                try:
                    kiloped = float(rec.get('KILOPED_C', 0) or 0)
                    entrega = float(rec.get('ENTREGA_C', 0) or 0)
                    liquiya = float(rec.get('LIQUIYA_C', 0) or 0)
                except (ValueError, TypeError) as e:
                    print(f"ERROR: Could not convert values to float for record {i}: {e}. Record data: {rec}")
                    continue

                if (entrega == liquiya and entrega != 0):
                    continue

                if kiloped > entrega:
                    cosecha = rec.get('COSECHA_C', 'N/A')
                    if min_harvest_year and cosecha < min_harvest_year:
                        continue

                    diferencia = kiloped - entrega
                    contrato = rec.get('NROCONT_C', 'N/A')
                    # Asegurarse de que el contrato es un string y quitar espacios
                    if isinstance(contrato, str):
                        contrato = contrato.strip()

                    grano_desc = rec.get('PRODUCT_C', 'N/A')
                    comprador = rec.get('APELCOM_C', 'N/A')
                    camiones = math.ceil(diferencia / 30000)

                    # Obtener la suma de kilos liquidados desde el diccionario pre-calculado
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

                    # Update totals per grain and harvest
                    if (grano_desc, cosecha) not in totales_por_grano_cosecha:
                        totales_por_grano_cosecha[(grano_desc, cosecha)] = {'kilos': 0, 'camiones': 0, 'kilos_liquidados': 0, 'kilos_liq_ventas': 0}
                    
                    totales_por_grano_cosecha[(grano_desc, cosecha)]['kilos'] += diferencia
                    totales_por_grano_cosecha[(grano_desc, cosecha)]['camiones'] += camiones
                    totales_por_grano_cosecha[(grano_desc, cosecha)]['kilos_liquidados'] += liquiya
                    totales_por_grano_cosecha[(grano_desc, cosecha)]['kilos_liq_ventas'] += kilos_liq_ventas

    except FileNotFoundError as e:
        print(f"Error: No se encontró el archivo DBF: {e.filename}")



    return contratos_pendientes, totales_por_grano_cosecha



@app.route('/ventas', methods=['GET', 'POST'])
def ventas():
    try:
        # --- New section for pending contracts ---
        current_year = datetime.date.today().year
        min_harvest_year_start = (current_year - 1) % 100
        min_harvest_year = f"{min_harvest_year_start:02d}/{(min_harvest_year_start + 1):02d}"
        contratos_pendientes, totales_por_grano_cosecha = get_contratos_pendientes(min_harvest_year=min_harvest_year)
        stock_granos_cosecha = get_stock_granos_por_cosecha()

        # Prepare data for pie chart (pending shipments by grain)
        totales_por_grano = {}
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
        
        # --- Cupos Solicitados ---
        db = get_db()
        with db:
            cursor = db.cursor()
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
        with DBF(RUTA_ACOCARPO_DBF, encoding='iso-8859-1') as tabla_acocarpo:
            for rec in tabla_acocarpo:
                contrato = rec.get('G_CONTRATO')
                fecha = rec.get('G_FECHA')
                if contrato and fecha:
                    if contrato not in latest_dates or fecha > latest_dates[contrato]:
                        latest_dates[contrato] = fecha
        
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
                with DBF(RUTA_ACOCARPO_DBF, encoding='iso-8859-1') as tabla_acocarpo:
                    registros_acocarpo = [rec for rec in tabla_acocarpo if rec['G_CONTRATO'] == g_contrato_filtro]
                    
                    if registros_acocarpo:
                        for rec in registros_acocarpo:
                            registro_ordenado = OrderedDict()
                            registro_ordenado['FECHA'] = format_date(rec.get('G_FECHA', ''))
                            registro_ordenado['Nro Interno'] = rec.get('G_ROMAN', '')
                            registro_ordenado['CTG'] = rec.get('G_CTG', '')
                            registro_ordenado['Kilos Netos'] = format_number(rec.get('G_SALDO', 0))
                            registro_ordenado['DESTINO'] = rec.get('G_DESTINO', '')
                            
                            if rec.get('G_CONFIRM', 'N').strip().upper() == 'S':
                                entregas_confirmadas.append(registro_ordenado)
                                total_confirmadas_num += rec.get('G_SALDO', 0) or 0
                            else:
                                entregas_no_confirmadas.append(registro_ordenado)
                                total_no_confirmadas_num += rec.get('G_SALDO', 0) or 0

                        total_saldo_num = total_confirmadas_num + total_no_confirmadas_num
                        
                        info_adicional = {
                            'grano': registros_acocarpo[0].get('G_CODI', 'N/A'),
                            'cosecha': registros_acocarpo[0].get('G_COSE', 'N/A')
                        }
                        grano_code = info_adicional['grano']
                        info_adicional['grano'] = get_grano_description(grano_code)

                with DBF(RUTA_LIQVEN_DBF, encoding='iso-8859-1') as tabla_liqven:
                    registros_liqven = [rec for rec in tabla_liqven if rec['CONTRATO'] == g_contrato_filtro]

                    if registros_liqven:
                        if info_adicional:
                            info_adicional['comprador'] = registros_liqven[0].get('NOM_C', 'N/A')
                        
                        liquidaciones_filtradas = []
                        sumas = { 'Peso': 0, 'N.Grav.': 0, 'IVA': 0, 'Otros': 0, 'Total': 0 }

                        for rec in registros_liqven:
                            fac_c_padded = str(rec.get('FAC_C', '')).zfill(8)
                            coe_val = f"{rec.get('FA1_C', '')}-{fac_c_padded}"
                            
                            otros_val_num = sum(rec.get(col, 0) or 0 for col in ['OTR_GAS', 'IVA_GAS', 'GAS_COM', 'IVA_COM', 'GAS_VAR', 'IVA_VAR'])

                            sumas['Peso'] += rec.get('PESO', 0) or 0
                            sumas['N.Grav.'] += rec.get('BRU_C', 0) or 0
                            sumas['IVA'] += rec.get('IVA_C', 0) or 0
                            sumas['Otros'] += otros_val_num
                            sumas['Total'] += rec.get('NET_CTA', 0) or 0

                            liquidacion_ordenada = OrderedDict()
                            liquidacion_ordenada['Fecha'] = format_date(rec.get('FEC_C', ''))
                            liquidacion_ordenada['COE'] = coe_val
                            liquidacion_ordenada['Peso'] = format_number(rec.get('PESO', 0))
                            liquidacion_ordenada['Precio'] = format_number(rec.get('PREOPE', 0), is_currency=True)
                            liquidacion_ordenada['N.Grav.'] = format_number(rec.get('BRU_C', 0), is_currency=True)
                            liquidacion_ordenada['IVA'] = format_number(rec.get('IVA_C', 0), is_currency=True)
                            liquidacion_ordenada['Otros'] = format_number(otros_val_num, is_currency=True)
                            liquidacion_ordenada['Total'] = format_number(rec.get('NET_CTA', 0), is_currency=True)
                            liquidaciones_filtradas.append(liquidacion_ordenada)
                        
                        total_liquidaciones = len(registros_liqven)
                        totales_liq_formatted = {key: format_number(val, is_currency=(key != 'Peso')) for key, val in sumas.items()}
                        total_peso = sumas['Peso']
                
                diferencia = total_saldo_num - total_peso
                if diferencia < 0:
                    camiones_restantes = math.ceil(abs(diferencia) / 30000)

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

@app.route('/cupos/solicitar', methods=['POST'])
def solicitar_cupo():
    try:
        data = request.json
        db = get_db()
        with db:
            db.execute("""
                INSERT INTO cupos_solicitados (contrato, grano, cosecha, cantidad, fecha_solicitud, nombre_persona)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                data['contrato'],
                data['grano'],
                data['cosecha'],
                data['cantidad'],
                data['fecha_solicitud'],
                data['nombre_persona']
            ))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/cupos/assign_trip', methods=['POST'])
def assign_trip():
    try:
        data = request.json
        db = get_db()
        with db:
            db.execute("UPDATE cupos_solicitados SET flete_id = ? WHERE id = ?", (data['flete_id'], data['cupo_id']))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/cupos/update_codigo', methods=['POST'])
def update_codigo():
    try:
        data = request.json
        db = get_db()
        with db:
            db.execute("UPDATE cupos_solicitados SET codigo_cupo = ? WHERE id = ?", (data['codigo_cupo'], data['cupo_id']))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def get_filtro_values():
    granos = {}
    cosechas = set()
    compradores = set()
    
    try:
        with DBF(RUTA_ACOGRAN_DBF, encoding='iso-8859-1') as tabla_acogran:
            for rec in tabla_acogran:
                if rec.get('G_CODI') and rec.get('G_DESC'):
                    granos[rec['G_CODI']] = rec['G_DESC'].strip()

        with DBF(RUTA_ACOCARPO_DBF, encoding='iso-8859-1') as tabla_acocarpo:
            for rec in tabla_acocarpo:
                if rec.get('G_COSE'):
                    cosechas.add(rec['G_COSE'].strip())
        
        with DBF(RUTA_CONTRAT_DBF, encoding='iso-8859-1') as tabla_contrat:
            for rec in tabla_contrat:
                if rec.get('APELCOM_C'):
                    compradores.add(rec['APELCOM_C'].strip())

    except FileNotFoundError as e:
        print(f"Error: No se encontró el archivo DBF: {e.filename}")
    except Exception as e:
        print(f"Ocurrió un error al leer el archivo: {e}")
        
    return sorted(granos.items()), sorted(list(cosechas), reverse=True), sorted(list(compradores))

def get_entregas(filtros):
    entregas = []
    total_kilos_netos = 0
    try:
        compradores_map = {}
        with DBF(RUTA_CONTRAT_DBF, encoding='iso-8859-1') as tabla_contrat:
            for rec in tabla_contrat:
                compradores_map[rec['NROCONT_C'].strip()] = rec['APELCOM_C'].strip()

        with DBF(RUTA_ACOCARPO_DBF, encoding='iso-8859-1') as tabla_acocarpo:
            for rec in tabla_acocarpo:
                fecha_entrega_str = rec.get('G_FECHA')
                if isinstance(fecha_entrega_str, (datetime.date)):
                    fecha_entrega = fecha_entrega_str
                else:
                    continue

                if filtros.get('fecha_desde') and fecha_entrega < datetime.datetime.strptime(filtros['fecha_desde'], '%Y-%m-%d').date():
                    continue
                if filtros.get('fecha_hasta') and fecha_entrega > datetime.datetime.strptime(filtros['fecha_hasta'], '%Y-%m-%d').date():
                    continue
                
                grano_code = rec.get('G_CODI')
                if filtros.get('grano') and grano_code != filtros['grano']:
                    continue

                cosecha = rec.get('G_COSE')
                if filtros.get('cosecha') and cosecha != filtros['cosecha']:
                    continue

                contrato = rec.get('G_CONTRATO', '').strip()
                nombre_comprador = compradores_map.get(contrato, '')
                if filtros.get('comprador') and nombre_comprador != filtros['comprador']:
                    continue
                
                kilos_netos = rec.get('G_SALDO', 0)
                total_kilos_netos += kilos_netos

                entrega = {
                    'fecha': format_date(fecha_entrega),
                    'contrato': contrato,
                    'comprador': nombre_comprador,
                    'grano': get_grano_description(grano_code),
                    'cosecha': cosecha,
                    'kilos_netos': format_number(kilos_netos),
                    'ctg': rec.get('G_CTG', ''),
                    'destino': rec.get('G_DESTINO', '')
                }
                entregas.append(entrega)

    except FileNotFoundError as e:
        print(f"Error: No se encontró el archivo DBF: {e.filename}")
    except Exception as e:
        print(f"Ocurrió un error al leer el archivo: {e}")

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
    try:
        with DBF(RUTA_ACOCARPO_DBF, encoding='iso-8859-1') as tabla_acocarpo:
            all_records = [rec for rec in tabla_acocarpo if rec.get('G_COSE') and rec.get('G_CONTRATO')]
            
            # Obtener las últimas 3 cosechas únicas y ordenarlas
            cosechas_unicas = sorted(list(set(rec['G_COSE'] for rec in all_records)), reverse=True)
            ultimas_tres_cosechas = cosechas_unicas[:3]
            
            # Filtrar contratos de las últimas tres cosechas y mantener el orden
            contratos_vistos = set()
            contratos_granaria = []
            # Iterar en reversa para obtener los contratos más recientes primero
            for rec in reversed(all_records):
                contrato = rec.get('G_CONTRATO').strip()
                if contrato and rec.get('G_COSE') in ultimas_tres_cosechas:
                    if contrato not in contratos_vistos:
                        contratos_granaria.append(contrato)
                        contratos_vistos.add(contrato)

    except FileNotFoundError:
        contratos_granaria = []
        print(f"Advertencia: No se encontró el archivo DBF: {RUTA_ACOCARPO_DBF}")
    except Exception as e:
        contratos_granaria = []
        print(f"Error al leer {RUTA_ACOCARPO_DBF}: {e}")


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
                # Obtener Entregas
                try:
                    with DBF(RUTA_ACOCARPO_DBF, encoding='iso-8859-1') as tabla_acocarpo:
                        for rec in tabla_acocarpo:
                            if rec['G_CONTRATO'] == g_contrato_filtro_granaria:
                                if isinstance(rec.get('G_FECHA'), datetime.date):
                                    movimientos.append({
                                        'fecha': rec['G_FECHA'],
                                        'comprobante': rec.get('G_CTG', ''),
                                        'descripcion': f"Entrega - CTG: {rec.get('G_CTG', '')}",
                                        'entregas': rec.get('G_SALDO', 0) or 0,
                                        'liquidaciones': 0
                                    })
                except Exception as e:
                    print(f"Error al leer {RUTA_ACOCARPO_DBF} para Cta Cte Granaria: {e}")

                # Obtener Liquidaciones
                try:
                    with DBF(RUTA_LIQVEN_DBF, encoding='iso-8859-1') as tabla_liqven:
                        for rec in tabla_liqven:
                            if rec['CONTRATO'] == g_contrato_filtro_granaria:
                                if isinstance(rec.get('FEC_C'), datetime.date):
                                    fac_c_padded = str(rec.get('FAC_C', '')).zfill(8)
                                    coe_val = f"{rec.get('FA1_C', '')}-{fac_c_padded}"
                                    movimientos.append({
                                        'fecha': rec['FEC_C'],
                                        'comprobante': coe_val,
                                        'descripcion': f"Liquidación - COE: {coe_val}",
                                        'entregas': 0,
                                        'liquidaciones': rec.get('PESO', 0) or 0
                                    })
                except Exception as e:
                    print(f"Error al leer {RUTA_LIQVEN_DBF} para Cta Cte Granaria: {e}")
                
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

    try:
        clientes_map = {}
        with DBF(RUTA_SYSMAE_DBF, encoding='iso-8859-1') as tabla_sysmae:
            for rec in tabla_sysmae:
                if rec.get('CLI_C') and rec.get('S_APELLI'):
                    clientes_map[rec['CLI_C'].strip()] = rec['S_APELLI'].strip()

        with DBF(RUTA_CCBCTA_DBF, encoding='iso-8859-1') as tabla_ccbcta:
            all_records = []
            for rec in tabla_ccbcta:
                fecha_vto = rec.get('VTO_F')
                if isinstance(fecha_vto, datetime.date) and fecha_desde_dt <= fecha_vto <= fecha_hasta_dt:
                    all_records.append(rec)

            # Sort all records by date and then by comprobante
            all_records.sort(key=lambda r: (r.get('VTO_F'), f"{r.get('FA1_F', '')}-{str(r.get('FAC_F', '')).zfill(8)}"))

            for rec in all_records:
                fecha_vto = rec.get('VTO_F')
                tip_f = rec.get('TIP_F', '').strip().upper()
                imp_f = rec.get('IMP_F', 0) or 0
                cliente_code = rec.get('CLI_F', '').strip()
                comprobante = f"{rec.get('FA1_F', '')}-{str(rec.get('FAC_F', '')).zfill(8)}"

                item = {
                    'vencimiento': format_date(fecha_vto),
                    'cliente': clientes_map.get(cliente_code, cliente_code),
                    'tipo': tip_f,
                    'comprobante': comprobante,
                    'importe': imp_f
                }

                if tip_f in ('LF', 'LP'):
                    vencimientos_list.append(item)
                    total_vencimientos += imp_f
                elif tip_f in ('RI', 'SI', 'SG', 'SB'):
                    cobranzas_list.append(item)
                    total_cobranzas += imp_f

    except FileNotFoundError as e:
        print(f"Advertencia: No se encontró el archivo DBF: {e.filename}")
    except Exception as e:
        print(f"Error al leer los archivos DBF: {e}")

    return render_template('cobranzas.html', 
                           filtros_aplicados=filtros_aplicados,
                           vencimientos=vencimientos_list,
                           cobranzas=cobranzas_list,
                           total_vencimientos=total_vencimientos,
                           total_cobranzas=total_cobranzas,
                           title="Cobranzas")

def importar_fletes_desde_dbf():
    try:
        with DBF(RUTA_ACOHIS_DBF, encoding='iso-8859-1') as tabla_acohis:
            fletes_data = []
            for rec in tabla_acohis:
                if rec.get('G_CUITRAN') == '30-68979922-8' and rec.get('G_CTL') == 'V':
                    cosecha = rec.get('G_COSE', '')
                    if cosecha and cosecha >= '20/21':
                        fletes_data.append(rec)

        db = get_db()
        with db:
            cursor = db.cursor()
            added_count = 0
            skipped_count = 0
            for rec in fletes_data:
                g_ctg = rec.get('G_CTG')
                if not g_ctg:
                    skipped_count += 1
                    continue

                cursor.execute("SELECT id FROM fletes WHERE g_ctg = ?", (g_ctg,))
                exists = cursor.fetchone()

                if exists:
                    skipped_count += 1
                    continue

                kilos_netos = rec.get('O_NETO', 0) or 0
                tarifa = rec.get('G_TARFLET', 0) or 0
                try:
                    kilos_netos_float = float(kilos_netos)
                except (ValueError, TypeError):
                    kilos_netos_float = 0.0
                try:
                    tarifa_float = float(tarifa)
                except (ValueError, TypeError):
                    tarifa_float = 0.0

                importe = (kilos_netos_float / 1000) * tarifa_float

                cursor.execute("""
                    INSERT INTO fletes (g_fecha, g_ctg, g_codi, g_cose, o_peso, o_neto, g_tarflet, g_kilomet, g_ctaplade, g_cuilchof, importe, fuente)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rec.get('G_FECHA').strftime('%Y-%m-%d') if isinstance(rec.get('G_FECHA'), datetime.date) else None,
                    g_ctg,
                    rec.get('G_CODI'),
                    rec.get('G_COSE'),
                    rec.get('O_PESO'),
                    kilos_netos_float,
                    tarifa_float,
                    rec.get('G_KILOMETR') *2,
                    rec.get('G_CTAPLADE'),
                    rec.get('G_CUILCHOF'),
                    importe,
                    'dbf'
                ))
                added_count += 1
        
        return f"Importación completada. {added_count} registros agregados, {skipped_count} registros omitidos (duplicados o sin CTG)."

    except FileNotFoundError:
        return f"Error: No se encontró el archivo DBF: {RUTA_ACOHIS_DBF}"
    except Exception as e:
        return f"Ocurrió un error durante la importación: {e}"

@app.route('/fletes/importar')
def importar_fletes_route():
    mensaje = importar_fletes_desde_dbf()
    return render_template('placeholder.html', title="Importar Fletes", message=mensaje, back_url=url_for('fletes'))

@app.route('/fletes/update_km', methods=['POST'])
def update_km():
    try:
        flete_id = request.form['id']
        km = request.form['km'] 
        
        db = get_db()
        with db:
            db.execute("UPDATE fletes SET g_kilomet = ? WHERE id = ?", (km, flete_id))
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/fletes/nuevo', methods=['GET', 'POST'])
def nuevo_flete():
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

            if o_peso <= o_tara:
                return "Error: Los Kilos Brutos deben ser mayores que los Kilos Tara."

            o_neto = o_peso - o_tara
            
            importe = (o_neto / 1000) * g_tarflet

            db = get_db()
            with db:
                db.execute("""
                    INSERT INTO fletes (g_fecha, g_ctg, g_codi, g_cose, o_peso, o_neto, g_tarflet, g_kilomet, g_ctaplade, g_cuilchof, importe, fuente)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (g_fecha, g_ctg, g_codi, g_cose, o_peso, o_neto, g_tarflet, g_kilomet, g_ctaplade, g_cuilchof, importe, 'manual'))
            
            return redirect(url_for('fletes'))
        except sqlite3.IntegrityError:
            return "Error: El CTG ya existe."
        except Exception as e:
            return f"Error al guardar el flete: {e}"

    # Para GET, obtener datos para los dropdowns
    granos_map = {}
    with DBF(RUTA_ACOGRAN_DBF, encoding='iso-8859-1') as tabla_acogran:
        for rec in tabla_acogran:
            granos_map[rec['G_CODI']] = rec['G_DESC'].strip()

    choferes_map = {}
    with DBF(RUTA_CHOFERES_DBF, encoding='iso-8859-1') as tabla_choferes:
        for rec in tabla_choferes:
            if rec.get('C_DOCUMENT') and rec.get('C_NOMBRE'):
                choferes_map[rec['C_DOCUMENT'].strip()] = rec['C_NOMBRE'].strip()
    
    # Ordenar choferes por nombre
    sorted_choferes = OrderedDict(sorted(choferes_map.items(), key=lambda item: item[1]))

    localidades_map = {}
    with DBF(RUTA_SYSMAE_DBF, encoding='iso-8859-1') as tabla_sysmae:
        for rec in tabla_sysmae:
            if rec.get('CLI_C') and rec.get('S_LOCALI'):
                localidades_map[rec['CLI_C'].strip()] = rec['S_LOCALI'].strip()

    # Ordenar localidades por nombre
    sorted_localidades = OrderedDict(sorted(localidades_map.items(), key=lambda item: item[1]))

    today_date = datetime.date.today().strftime('%Y-%m-%d')
            
    return render_template('nuevo_flete.html', 
                           granos=granos_map, 
                           choferes=sorted_choferes, 
                           localidades=sorted_localidades,
                           today_date=today_date)

@app.route('/fletes', methods=['GET', 'POST'])
def fletes():
    try:
        # --- Mapeo de Granos, Localidades, Choferes (se mantiene igual) ---
        granos_map = {}
        with DBF(RUTA_ACOGRAN_DBF, encoding='iso-8859-1') as tabla_acogran:
            for rec in tabla_acogran:
                granos_map[rec['G_CODI']] = rec['G_DESC'].strip()

        localidades_map = {}
        with DBF(RUTA_SYSMAE_DBF, encoding='iso-8859-1') as tabla_sysmae:
            for rec in tabla_sysmae:
                localidades_map[rec['CLI_C']] = rec['S_LOCALI'].strip()

        choferes_map = {}
        with DBF(RUTA_CHOFERES_DBF, encoding='iso-8859-1') as tabla_choferes:
            for rec in tabla_choferes:
                choferes_map[rec['C_DOCUMENT'].strip()] = rec['C_NOMBRE'].strip()
        
        # Obtener CUILs de choferes que tienen registros en la tabla 'fletes'
        db = get_db()
        cuils_con_registros = set()
        with db:
            cursor = db.cursor()
            cursor.execute("SELECT DISTINCT g_cuilchof FROM fletes WHERE g_cuilchof IS NOT NULL AND g_cuilchof != ''")
            for row in cursor.fetchall():
                cuils_con_registros.add(row['g_cuilchof'].strip())

        # Filtrar choferes_map para incluir solo aquellos con registros
        choferes_filtrados = {
            cuil: nombre for cuil, nombre in choferes_map.items()
            if cuil in cuils_con_registros
        }

        choferes_set = set(choferes_filtrados.keys())

        # --- Obtener datos desde la base de datos ---
        db = get_db()
        cursor = db.cursor()
        
        query = "SELECT * FROM fletes"
        params = []

        filtros_aplicados = {}
        if request.method == 'POST':
            filtros_aplicados['fecha_desde'] = request.form.get('fecha_desde')
            filtros_aplicados['fecha_hasta'] = request.form.get('fecha_hasta')
            chofer_seleccionado = request.form.get('chofer')
            filtros_aplicados['chofer'] = chofer_seleccionado

            conditions = []
            if filtros_aplicados.get('fecha_desde'):
                conditions.append("g_fecha >= ?")
                params.append(filtros_aplicados['fecha_desde'])
            if filtros_aplicados.get('fecha_hasta'):
                conditions.append("g_fecha <= ?")
                params.append(filtros_aplicados['fecha_hasta'])
            if chofer_seleccionado:
                conditions.append("g_cuilchof = ?")
                params.append(chofer_seleccionado)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        else:
            # --- Fechas por defecto para GET ---
            today = datetime.date.today()
            first_day_of_month = today.replace(day=1)
            filtros_aplicados['fecha_desde'] = first_day_of_month.strftime('%Y-%m-%d')
            filtros_aplicados['fecha_hasta'] = today.strftime('%Y-%m-%d')
            
            query += " WHERE g_fecha >= ? AND g_fecha <= ?"
            params.extend([filtros_aplicados['fecha_desde'], filtros_aplicados['fecha_hasta']])

        query += " ORDER BY g_cuilchof, g_fecha, g_ctg"
        
        cursor.execute(query, params)
        fletes_data = cursor.fetchall()

        # --- Procesamiento final y formato ---
        fletes_procesados = []
        total_neto = 0
        total_km = 0
        total_importe = 0
        viajes_con_kilos = 0
        for rec in fletes_data:
            kilos_netos = rec['o_neto'] or 0
            if kilos_netos != 0:
                viajes_con_kilos += 1

            tarifa = rec['g_tarflet'] or 0
            
            importe = (kilos_netos / 1000) * tarifa
            
            kilometros = rec['g_kilomet'] or 0
            total_neto += kilos_netos
            total_km += kilometros
            total_importe += importe
            
            flete = {
                'id': rec['id'],
                'G_FECHA': format_date(datetime.datetime.strptime(rec['g_fecha'], '%Y-%m-%d').date()),
                'G_CTG': rec['g_ctg'],
                'grano': granos_map.get(rec['g_codi'], rec['g_codi']),
                'G_COSE': rec['g_cose'],
                'O_PESO': format_number(rec['o_peso']),
                'O_NETO': format_number(kilos_netos),
                'G_TARFLET': format_number(tarifa, is_currency=True),
                'G_KILOMETR': kilometros,
                'localidad': localidades_map.get(rec['g_ctaplade'], 'N/A'),
                'importe': format_number(importe, is_currency=True),
                'fuente': rec['fuente']
            }
            fletes_procesados.append(flete)

        totales = {
            'viajes': viajes_con_kilos,
            'neto': format_number(total_neto),
            'km': total_km,
            'importe': format_number(total_importe, is_currency=True)
        }
        
        nombre_chofer_seleccionado = None
        if filtros_aplicados.get('chofer'):
            nombre_chofer_seleccionado = choferes_map.get(filtros_aplicados['chofer'])

        # Crear diccionario de localidades unicas ordenado por nombre
        sorted_localidades = OrderedDict(sorted(localidades_map.items(), key=lambda item: item[1]))
        unique_localidades = OrderedDict()
        seen_names = set()
        for code, name in sorted_localidades.items():
            if name not in seen_names:
                unique_localidades[code] = name
                seen_names.add(name)

        # Ordenar choferes por nombre para el modal
        sorted_all_choferes = OrderedDict(sorted(choferes_map.items(), key=lambda item: item[1]))

        return render_template('fletes.html', 
                               fletes=fletes_procesados, 
                               choferes=sorted(list(choferes_set)),
                               filtros_aplicados=filtros_aplicados,
                               nombre_chofer=nombre_chofer_seleccionado,
                               totales=totales,
                               granos=granos_map,
                               all_choferes=sorted_all_choferes,
                               localidades=unique_localidades)

    except Exception as e:
        return f"<h1>Ocurrió un error: {e}</h1>"

@app.route('/pdf/<tipo_reporte>')
def generar_pdf(tipo_reporte):
    contrato = request.args.get('contrato')
    if not contrato:
        return "Error: No se especificó un contrato.", 400

    if tipo_reporte == 'entregas':
        dbf_path = RUTA_ACOCARPO_DBF
        filter_column = 'G_CONTRATO'
        title = f'Reporte de Entregas - Contrato {contrato}'
        headers = ['FECHA', 'Nro Interno', 'CTG', 'Kilos Netos', 'DESTINO']
    elif tipo_reporte == 'liquidaciones':
        dbf_path = RUTA_LIQVEN_DBF
        filter_column = 'CONTRATO'
        title = f'Reporte de Liquidaciones - Contrato {contrato}'
        headers = ['Fecha', 'COE', 'Peso', 'Precio', 'N.Grav.', 'IVA', 'Otros', 'Total']
    else:
        return "Error: Tipo de reporte no válido.", 400

    temp_filename = f"c:/Tests/Acopio/temp_{tipo_reporte}_{contrato}.pdf"

    try:
        with DBF(dbf_path, encoding='iso-8859-1') as tabla:
            registros = [registro for registro in tabla if registro[filter_column] == contrato]

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

            key_map = {'FECHA': 'G_FECHA', 'Nro Interno': 'G_ROMAN', 'CTG': 'G_CTG', 'Kilos Netos': 'G_SALDO', 'DESTINO': 'G_DESTINO'}

            for registro in registros:
                row_data = OrderedDict()
                for header, dbf_key in key_map.items():
                    value = registro.get(dbf_key, '')
                    if 'FECHA' in header.upper():
                        value = format_date(value)
                    elif header == 'Kilos Netos':
                        value = format_number(value)
                    row_data[header] = value

                if registro.get('G_CONFIRM', 'N').strip().upper() == 'S':
                    row_data['confirmed'] = True
                    entregas_confirmadas_pdf.append(row_data)
                    total_confirmadas_pdf += registro.get('G_SALDO', 0) or 0
                else:
                    row_data['confirmed'] = False
                    entregas_no_confirmadas_pdf.append(row_data)
                    total_no_confirmadas_pdf += registro.get('G_SALDO', 0) or 0
            
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
                otros_val_num = sum(registro.get(col, 0) or 0 for col in ['OTR_GAS', 'IVA_GAS', 'GAS_COM', 'IVA_COM', 'GAS_VAR', 'IVA_VAR'])
                sumas_pdf['Peso'] += registro.get('PESO', 0) or 0
                sumas_pdf['N.Grav.'] += registro.get('BRU_C', 0) or 0
                sumas_pdf['IVA'] += registro.get('IVA_C', 0) or 0
                sumas_pdf['Otros'] += otros_val_num
                sumas_pdf['Total'] += registro.get('NET_CTA', 0) or 0

                fac_c_padded = str(registro.get('FAC_C', '')).zfill(8)
                coe_val = f"{rec.get('FA1_C', '')}-{fac_c_padded}"

                row_data = OrderedDict()
                row_data['Fecha'] = format_date(registro.get('FEC_C', ''))
                row_data['COE'] = coe_val
                row_data['Peso'] = format_number(registro.get('PESO', 0))
                row_data['Precio'] = format_number(registro.get('PREOPE', 0), is_currency=True)
                row_data['N.Grav.'] = format_number(rec.get('BRU_C', 0), is_currency=True)
                row_data['IVA'] = format_number(rec.get('IVA_C', 0), is_currency=True)
                row_data['Otros'] = format_number(otros_val_num, is_currency=True)
                row_data['Total'] = format_number(rec.get('NET_CTA', 0), is_currency=True)
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

    except FileNotFoundError:
        return f"<h1>Error: No se encontró el archivo DBF para el reporte.</h1>", 404
    except Exception as e:
        return f"<h1>Ocurrió un error al generar el PDF: {e}</h1>", 500
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@app.route('/test_choferes')
def test_choferes():
    try:
        with DBF(RUTA_CHOFERES_DBF, encoding='iso-8859-1') as tabla_choferes:
            return str(next(iter(tabla_choferes)))
    except Exception as e:
        return str(e)

@app.route('/debug-acohis-last10')
def debug_acohis_last10():
    try:
        with DBF(RUTA_ACOHIS_DBF, encoding='iso-8859-1') as tabla_acohis:
            all_records = list(tabla_acohis) # Read all records into a list
            last_10_records = all_records[-10:] # Get the last 10 records

            formatted_records = []
            for rec in last_10_records:
                formatted_rec = {}
                for field_name, value in rec.items():
                    if isinstance(value, datetime.date):
                        formatted_rec[field_name] = value.strftime('%Y-%m-%d')
                    else:
                        formatted_rec[field_name] = value
                formatted_records.append(formatted_rec)

            return render_template('debug.html', records=formatted_records, dbf_name="acohis.dbf")

    except FileNotFoundError:
        return f"<h1>Error: No se encontró el archivo DBF: {RUTA_ACOHIS_DBF}</h1>"
    except Exception as e:
        return f"<h1>Ocurrió un error al leer el archivo: {e}</h1>"

@app.route('/fletes/<int:flete_id>')
def get_flete(flete_id):
    db = get_db()
    flete = db.execute('SELECT * FROM fletes WHERE id = ?', (flete_id,)).fetchone()
    if flete is None:
        return jsonify({'error': 'Flete not found'}), 404
    
    # Convert row object to a dictionary
    flete_dict = dict(flete)
    return jsonify(flete_dict)

@app.route('/fletes/edit/<int:flete_id>', methods=['POST'])
def edit_flete(flete_id):
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

        if o_peso <= o_tara:
            return "Error: Los Kilos Brutos deben ser mayores que los Kilos Tara."

        o_neto = o_peso - o_tara
        
        importe = (o_neto / 1000) * g_tarflet

        db = get_db()
        with db:
            db.execute("""
                UPDATE fletes 
                SET g_fecha = ?, g_ctg = ?, g_codi = ?, g_cose = ?, o_peso = ?, o_neto = ?, g_tarflet = ?, g_kilomet = ?, g_ctaplade = ?, g_cuilchof = ?, importe = ?
                WHERE id = ?
            """, (g_fecha, g_ctg, g_codi, g_cose, o_peso, o_neto, g_tarflet, g_kilomet, g_ctaplade, g_cuilchof, importe, flete_id))
        
        return redirect(url_for('fletes'))
    except sqlite3.IntegrityError:
        return "Error: El CTG ya existe."
    except Exception as e:
        return f"Error al editar el flete: {e}"

@app.route('/fletes/delete/<int:flete_id>', methods=['POST'])
def delete_flete(flete_id):
    try:
        db = get_db()
        with db:
            db.execute("DELETE FROM fletes WHERE id = ?", (flete_id,))
        return redirect(url_for('fletes'))
    except Exception as e:
        return f"Error al eliminar el flete: {e}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)