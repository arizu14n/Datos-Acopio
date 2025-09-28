# Sistema de Gestión de Acopio

Una aplicación web desarrollada en Python con Flask para centralizar, analizar y gestionar datos de una empresa de acopio. El sistema actúa como un puente entre archivos de bases de datos heredadas (formato `.dbf`) y una interfaz de usuario moderna, enriqueciendo los datos con una base de datos relacional (SQLite) y servicios externos.



## 🚀 Características Principales

- **Dashboard Gerencial**: Visualización rápida de los indicadores clave de rendimiento (KPIs) del negocio: total de fletes, ventas, estado de stock y cobranzas en un período determinado.
- **Módulo de Ventas**: Análisis profundo de contratos, seguimiento de entregas (confirmadas y no confirmadas), liquidaciones y cálculo de saldos pendientes. Incluye gráficos comparativos y exportación a PDF.
- **Módulo de Fletes**: Sistema CRUD (Crear, Leer, Actualizar, Borrar) completo para la gestión de viajes. Incluye una función para migrar datos históricos desde archivos `.dbf` a la base de datos SQLite, evitando duplicados.
- **Módulo de Consultas Dinámicas**:
    - Búsqueda y filtrado avanzado de entregas por fecha, grano, cosecha y comprador.
    - Integración con servicios externos mediante *web scraping* (Selenium) para consultar el padrón de SISA de la AFIP en tiempo real.
- **Módulo de Cobranzas**: Resumen detallado de facturas por vencer y pagos recibidos, facilitando la gestión del flujo de caja.

## 🛠️ Tecnologías Utilizadas

- **Backend**: Python, Flask
- **Base de Datos**: SQLite (para datos nuevos/migrados) y `dbfread` para lectura de archivos `.dbf`.
- **Frontend**: HTML, CSS, JavaScript, Chart.js (para gráficos).
- **Web Scraping**: Selenium, BeautifulSoup4.
- **Generación de Reportes**: FPDF2.

---

## ⚙️ Instalación y Puesta en Marcha

Sigue estos pasos para ejecutar el proyecto en tu entorno local.

### 1. Prerrequisitos

- Python 3.8 o superior.
- `pip` (el gestor de paquetes de Python).
- Google Chrome (necesario para el web scraping con Selenium).

### 2. Clonar el Repositorio

```bash
git clone <URL_DEL_REPOSITORIO>
cd <NOMBRE_DEL_DIRECTORIO>
```

### 3. Crear y Activar un Entorno Virtual

Es una buena práctica aislar las dependencias del proyecto.

```bash
# En Windows
python -m venv venv
.\venv\Scripts\activate

# En macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Instalar Dependencias

Instala todas las librerías de Python necesarias con el siguiente comando:

```bash
pip install -r requirements.txt
```

### 5. Configurar Rutas de Archivos DBF

La aplicación necesita acceder a los archivos `.dbf`. Asegúrate de que las rutas definidas al principio del archivo `app.py` sean correctas para tu sistema.

```python
# app.py

# --- CONFIGURACIÓN DE RUTAS ---
RUTA_ACOCARPO_DBF = "C:\\acocta5\\acocarpo.dbf"
RUTA_LIQVEN_DBF = "C:\\acocta5\\liqven.dbf"
# ... y las demás rutas
```

### 6. Inicializar la Base de Datos

La aplicación utiliza una base de datos SQLite para el módulo de fletes. Ejecuta el siguiente comando para crear la base de datos y la tabla `fletes`.

```bash
flask init-db
```

### 7. Ejecutar la Aplicación

Puedes iniciar el servidor de desarrollo de Flask de dos maneras:

**Opción A: Usando el comando de Flask**

```bash
flask run --host=0.0.0.0
```

**Opción B: Usando el script `start_server.bat` (solo para Windows)**

Simplemente haz doble clic en el archivo `start_server.bat`. Esto iniciará el servidor y abrirá la aplicación en tu navegador automáticamente.

Una vez iniciado, accede a la aplicación en `http://127.0.0.1:5000/`.

---

## 📖 Uso

- **Importar Fletes Históricos**: Para poblar la base de datos de fletes por primera vez, navega a la sección de "Fletes" y utiliza la opción de "Importar desde DBF". Esto leerá el archivo `acohis.dbf` y cargará los datos relevantes en la base de datos SQLite.
- **Navegación**: Utiliza la barra de navegación superior para moverte entre los diferentes módulos: Dashboard, Ventas, Fletes, Consultas y Cobranzas.
- **Filtros**: La mayoría de las páginas contienen filtros (por fecha, chofer, etc.) para acotar los datos mostrados. No olvides hacer clic en "Consultar" después de seleccionarlos.
- **Exportación a PDF**: En la página de "Ventas", después de seleccionar un contrato, encontrarás botones para exportar los reportes de entregas y liquidaciones a formato PDF.