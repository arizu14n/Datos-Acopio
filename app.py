# app.py

from flask import Flask, render_template, request, Response
from dbfread import DBF
from collections import OrderedDict
from fpdf import FPDF
import datetime
import os
import locale
from decimal import Decimal
import math

# --- CONFIGURACIÓN DE LOCALIZACIÓN PARA FORMATO DE NÚMEROS ---
try:
    locale.setlocale(locale.LC_ALL, 'es_AR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'Spanish_Argentina.1252')
    except locale.Error:
        print("Advertencia: No se pudo establecer la localización a es_AR. Los formatos de número pueden ser incorrectos.")

app = Flask(__name__)

# --- CONFIGURACIÓN DE RUTAS ---
RUTA_ACOCARPO_DBF = "C:\\acocta5\\acocarpo.dbf"
RUTA_LIQVEN_DBF = "C:\\acocta5\\liqven.dbf"
RUTA_ACOGRAN_DBF = "C:\\acocta5\\acogran.dbf"
RUTA_ACOGRAST_DBF = "C:\\acocta5\\acograst.dbf"

def format_date(date_obj):
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

def get_contratos_pendientes():
    contratos_pendientes = []
    totales_por_grano_cosecha = {}
    
    try:
        with DBF(RUTA_ACOCARPO_DBF, encoding='iso-8859-1') as tabla_acocarpo, \
             DBF(RUTA_LIQVEN_DBF, encoding='iso-8859-1') as tabla_liqven:

            # Cache data from DBF files to avoid re-reading
            all_acocarpo_recs = list(tabla_acocarpo)
            all_liqven_recs = list(tabla_liqven)

            contratos = sorted(list(set(rec['G_CONTRATO'] for rec in all_acocarpo_recs)))

            for contrato in contratos:
                # Calculate total delivered
                total_saldo_num = sum(rec['G_SALDO'] for rec in all_acocarpo_recs if rec['G_CONTRATO'] == contrato and rec['G_SALDO'] is not None)

                # Calculate total liquidated
                total_peso = sum(rec['PESO'] for rec in all_liqven_recs if rec['CONTRATO'] == contrato and rec['PESO'] is not None)

                diferencia = total_saldo_num - total_peso

                if diferencia < 0:
                    # Get contract details
                    acocarpo_rec = next((rec for rec in all_acocarpo_recs if rec['G_CONTRATO'] == contrato), None)
                    liqven_rec = next((rec for rec in all_liqven_recs if rec['CONTRATO'] == contrato), None)

                    if acocarpo_rec:
                        grano_code = acocarpo_rec.get('G_CODI', 'N/A')
                        cosecha = acocarpo_rec.get('G_COSE', 'N/A')
                        grano_desc = get_grano_description(grano_code)
                        comprador = liqven_rec.get('NOM_C', 'N/A') if liqven_rec else 'N/A'
                        camiones = math.ceil(abs(diferencia) / 30000)

                        contrato_info = {
                            'contrato': contrato,
                            'comprador': comprador,
                            'grano': grano_desc,
                            'cosecha': cosecha,
                            'kilos_liquidados': format_number(total_peso),
                            'kilos_pendientes': format_number(diferencia),
                            'camiones_pendientes': camiones
                        }
                        contratos_pendientes.append(contrato_info)

                        # Update totals per grain and harvest
                        if (grano_desc, cosecha) not in totales_por_grano_cosecha:
                            totales_por_grano_cosecha[(grano_desc, cosecha)] = {'kilos': 0, 'camiones': 0, 'kilos_liquidados': 0}
                        totales_por_grano_cosecha[(grano_desc, cosecha)]['kilos'] += abs(diferencia)
                        totales_por_grano_cosecha[(grano_desc, cosecha)]['camiones'] += camiones
                        totales_por_grano_cosecha[(grano_desc, cosecha)]['kilos_liquidados'] += total_peso

    except FileNotFoundError as e:
        print(f"Error: No se encontró el archivo DBF: {e.filename}")
    except Exception as e:
        print(f"Ocurrió un error al procesar los contratos: {e}")

    return contratos_pendientes, totales_por_grano_cosecha




@app.route('/ventas', methods=['GET', 'POST'])
def ventas():
    try:
        # --- New section for pending contracts ---
        contratos_pendientes, totales_por_grano_cosecha = get_contratos_pendientes()
        stock_granos_cosecha = get_stock_granos_por_cosecha()

        # Prepare data for pie chart (pending shipments by grain)
        totales_por_grano = {}
        for (grano, cosecha), data in totales_por_grano_cosecha.items():
            if grano not in totales_por_grano:
                totales_por_grano[grano] = {'kilos': 0, 'camiones': 0, 'kilos_liquidados': 0}
            totales_por_grano[grano]['kilos'] += data['kilos']
            totales_por_grano[grano]['camiones'] += data['camiones']
            totales_por_grano[grano]['kilos_liquidados'] += data['kilos_liquidados']
            
        pie_chart_labels = list(totales_por_grano.keys())
        pie_chart_values = [totales_por_grano[key]['kilos'] for key in pie_chart_labels]

        # Prepare data for bar chart (pending vs stock by grain and harvest)
        bar_chart_labels = [f"{grano} ({cosecha})" for (grano, cosecha) in totales_por_grano_cosecha.keys()]
        bar_chart_pendientes = [data['kilos'] for data in totales_por_grano_cosecha.values()]
        bar_chart_stock = [stock_granos_cosecha.get((grano, cosecha), 0) for (grano, cosecha) in totales_por_grano_cosecha.keys()]
        
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

@app.route('/cobranzas')
def cobranzas():
    return render_template('placeholder.html', title="Cobranzas")

@app.route('/fletes')
def fletes():
    return render_template('placeholder.html', title="Fletes")

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
                coe_val = f"{registro.get('FA1_C', '')}-{fac_c_padded}"

                row_data = OrderedDict()
                row_data['Fecha'] = format_date(registro.get('FEC_C', ''))
                row_data['COE'] = coe_val
                row_data['Peso'] = format_number(registro.get('PESO', 0))
                row_data['Precio'] = format_number(registro.get('PREOPE', 0), is_currency=True)
                row_data['N.Grav.'] = format_number(registro.get('BRU_C', 0), is_currency=True)
                row_data['IVA'] = format_number(registro.get('IVA_C', 0), is_currency=True)
                row_data['Otros'] = format_number(otros_val_num, is_currency=True)
                row_data['Total'] = format_number(registro.get('NET_CTA', 0), is_currency=True)
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

if __name__ == '__main__':
    app.run(debug=True)
