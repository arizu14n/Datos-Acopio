# Ayuda Memoria - Presentación del Proyecto

*Este es un guion personal para la presentación. No es para mostrar al profesor.*

---

## Parte 1: El Pantallazo Inicial (La Visión)

*(Mientras muestras la aplicación corriendo, idealmente el Dashboard)*

1.  **Nombre del Proyecto:** Sistema de Gestión de Acopio.
2.  **Tecnología Principal:** Aplicación web construida en **Python** con el micro-framework **Flask**.
3.  **Problema que Resuelve:**
    *   Centraliza información dispersa.
    *   Moderniza el acceso a datos heredados (archivos **DBF**).
    *   Crea un puente entre sistemas antiguos y una interfaz de usuario moderna.

4.  **Módulos Clave (recorrerlos visualmente si es posible):**
    *   **Dashboard:** Vista gerencial con KPIs (Fletes, Ventas, Stock, Cobranzas).
    *   **Ventas:** Análisis de contratos, saldos pendientes y comparación con stock.
    *   **Fletes:** **CRUD completo** (Crear, Leer, Actualizar, Borrar) y **migración de datos** desde DBF a SQLite.
    *   **Consultas Dinámicas:** Búsqueda avanzada y **Web Scraping** a la AFIP (SISA) con Selenium.
    *   **Cobranzas:** Gestión de flujo de caja (facturas por vencer y pagos).

5.  **Cierre del Pantallazo:**
    *   "No es solo un lector de archivos, es una **solución integral** que centraliza, procesa, enriquece y presenta datos para la toma de decisiones."

---

## Parte 2: Explicación Técnica (Funciones Clave)

*(Navega al código o a la parte de la app que corresponda mientras explicas)*

### 1. Arquitectura Híbrida de Datos (`/dashboard`)

*   **Punto Clave:** El sistema trabaja con dos fuentes de datos al mismo tiempo.
*   **Fuente 1 (Moderna):** Base de datos **SQLite** para los fletes.
    *   Se conecta con `get_db()`.
    *   Usa consultas **SQL** para agregar totales (`SUM`, `COUNT`). Rápido y eficiente.
*   **Fuente 2 (Heredada):** Archivos **`.dbf`** para ventas y stock.
    *   Usa la librería `dbfread`.
    *   Manejo seguro con `with DBF(...) as tabla:`, que garantiza el cierre del archivo.
    *   Los cálculos se hacen en memoria (Python).
*   **Demuestra:** Capacidad de integrar sistemas de datos dispares.

### 2. Lógica de Negocio Compleja (`get_contratos_pendientes`)

*   **Punto Clave:** El sistema no solo muestra datos, genera nueva información de valor.
*   **Paso 1 (Eficiencia):** **Pre-procesa** las liquidaciones. Lee `liqven.dbf` una sola vez y guarda los totales en un **diccionario de Python**. Esto evita lecturas repetitivas y lentas dentro de un bucle.
*   **Paso 2 (Lógica):** Aplica la regla de negocio: `kilos_pedidos > kilos_entregados`.
*   **Paso 3 (Enriquecimiento):** Calcula un dato nuevo y útil: `camiones_pendientes` usando `math.ceil`.
*   **Demuestra:** Traducción de una regla de negocio real a un algoritmo eficiente.

### 3. Web Scraping e Interacción Externa (`/consultas` - SISA)

*   **Punto Clave:** El sistema se conecta a servicios externos que no tienen API.
*   **Herramientas:** **Selenium** (para controlar el navegador) y **BeautifulSoup** (para parsear el HTML).
*   **Proceso Clave:**
    1.  **Automatización:** Controla Chrome en modo **headless** (sin interfaz gráfica).
    2.  **Manejo de Tiempos (Importante):** Usa `WebDriverWait` en lugar de `time.sleep()`. Esto es más robusto porque espera a que los elementos *realmente* aparezcan, no un tiempo fijo.
    3.  **Extracción:** Una vez cargada la página, pasa el HTML a `BeautifulSoup` para extraer la tabla de forma estructurada.
    4.  **Robustez:** Todo está envuelto en un `try...except...finally`. El bloque `finally` asegura que el navegador (`driver.quit()`) **siempre se cierre**, incluso si hay un error, para no dejar procesos colgados.
*   **Demuestra:** Capacidad de interactuar con el mundo exterior y superar la falta de APIs.

### 4. Migración y Gestión de Datos (`/fletes`)

*   **Punto Clave:** Muestra un ciclo de vida de datos completo: desde lo antiguo a lo moderno.
*   **Paso 1 (Definición):** Se crea la tabla en SQLite con una restricción `UNIQUE` en la columna `g_ctg` (Carta de Porte). Esto es la **clave para no duplicar datos**.
*   **Paso 2 (Migración):** La función `importar_fletes_desde_dbf` es **idempotente**.
    *   ¿Qué significa? Se puede ejecutar muchas veces sin corromper los datos.
    *   ¿Cómo? Antes de insertar, hace un `SELECT` para ver si el CTG ya existe. Si existe, lo omite.
*   **Paso 3 (Gestión):** Una vez los datos están en SQLite, se implementa un **CRUD completo** (rutas `/nuevo`, `/edit`, `/delete`) para su gestión moderna.
*   **Demuestra:** Conocimiento de bases de datos, integridad de datos y creación de un ciclo de vida completo para una entidad.

---

### Cierre Final

**"Con estas funciones, busqué demostrar no solo el uso de librerías, sino también un pensamiento arquitectónico para resolver un problema real, integrando sistemas, aplicando lógica de negocio y asegurando la calidad de los datos."**