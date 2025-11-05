# Ayuda Memoria - Presentación del Proyecto

*Este es un guion personal para la presentación. No es para mostrar al profesor.*

---

## Parte 1: El Pantallazo Inicial (La Visión del Producto)

*(Mientras muestras la aplicación corriendo, idealmente el Dashboard)*

1.  **Nombre del Proyecto:** Sistema de Gestión de Acopio.
2.  **Tecnología Principal:** Aplicación web construida en **Python** con el micro-framework **Flask**.
3.  **Problema que Resuelve:**
    *   Centraliza información dispersa.
    *   Moderniza el acceso a datos heredados (archivos **DBF**).
    *   **Va más allá de la simple lectura:** Permite la **gestión activa** y la **creación de nuevos datos** que interactúan con la lógica de negocio existente.

4.  **Módulos Clave (recorrerlos visualmente si es posible):**
    *   **Dashboard:** Vista gerencial con KPIs (Fletes, Ventas, Stock, Cobranzas).
    *   **Ventas:** Análisis de contratos pendientes y un nuevo **flujo de trabajo interactivo para la solicitud de cupos de entrega**.
    *   **Fletes:** **CRUD completo** (Crear, Leer, Actualizar, Borrar) sobre una base de datos moderna (SQLite), con una **migración inicial idempotente** desde los DBF.
    *   **Consultas Dinámicas:**
        *   Búsqueda avanzada de entregas.
        *   **Web Scraping** a la AFIP (SISA) con Selenium.
        *   **Nueva Consulta de Cuenta Corriente Granaria** por contrato.
    *   **Cobranzas:** Gestión de flujo de caja (facturas por vencer y pagos).

5.  **Cierre del Pantallazo:**
    *   "No es solo un lector de archivos, es una **plataforma de gestión** que centraliza, procesa, enriquece y, lo más importante, **permite actuar** sobre los datos para optimizar la operación diaria."

---

## Parte 2: Explicación Técnica (Capacidades Demostradas)

*(Navega al código o a la parte de la app que corresponda mientras explicas)*

### 1. Arquitectura de Datos Híbrida y Progresiva (`/dashboard`, `/fletes`)

*   **Punto Clave:** El sistema no solo lee de fuentes dispares, sino que implementa una estrategia de **modernización progresiva**.
*   **Paso 1 (Lectura de Legado):** Lee archivos `.dbf` de forma segura (`dbfread`) para obtener datos de ventas, stock y cobranzas.
*   **Paso 2 (Migración Controlada):** La función `importar_fletes_desde_dbf` es **idempotente**. Usa una restricción `UNIQUE` en la base de datos y una comprobación `SELECT` previa para migrar datos históricos desde un DBF a SQLite **una sola vez**, evitando duplicados.
*   **Paso 3 (Gestión Moderna):** Una vez migrados, los fletes se gestionan con un **CRUD completo** sobre la base de datos SQLite, demostrando el ciclo de vida completo de los datos.
*   **Demuestra:** Una estrategia de migración realista, integridad de datos (`UNIQUE`, idempotencia) y la capacidad de construir funcionalidades modernas sobre datos heredados.

### 2. Flujo de Trabajo Interactivo y Creación de Datos (`/ventas` - Cupos)

*   **Punto Clave:** La aplicación no es pasiva; permite a los usuarios **iniciar acciones** que generan nuevos datos.
*   **Proceso:**
    1.  **Identificación:** El sistema identifica contratos con saldos pendientes (`get_contratos_pendientes`).
    2.  **Acción del Usuario:** El usuario hace clic en "Pedir Cupos", lo que abre un modal.
    3.  **Creación de Datos:** Al enviar el formulario, se crea un nuevo registro en la tabla `cupos_solicitados` de SQLite mediante una llamada **AJAX** (`fetch`). Esto no recarga la página.
    4.  **Gestión del Flujo:** Los cupos solicitados aparecen en una nueva tabla, donde se les puede asignar un viaje (vinculándolo a un flete de la otra tabla) o eliminar.
*   **Demuestra:** Creación de un flujo de trabajo completo, uso de una base de datos relacional para gestionar estados, y una experiencia de usuario moderna con interacciones AJAX.

### 3. Generación de Reportes Complejos y Dinámicos (`/consultas` - Cta. Cte. Granaria)

*   **Punto Clave:** El sistema puede consolidar información de múltiples fuentes para crear una vista unificada que no existe en el sistema original.
*   **Proceso:**
    1.  **Recolección de Entregas:** Lee el archivo `acocarpo.dbf` para obtener todos los movimientos de entrega de un contrato.
    2.  **Recolección de Liquidaciones:** Lee el archivo `liqven.dbf` para obtener todos los movimientos de liquidación del mismo contrato.
    3.  **Consolidación y Orden:** Combina ambas listas de movimientos en una sola, y la **ordena cronológicamente por fecha**.
    4.  **Cálculo de Saldo Corriente:** Itera sobre la lista unificada, calculando un saldo acumulativo (`saldo += entregas - liquidaciones`) en cada paso.
*   **Demuestra:** Capacidad para sintetizar datos de múltiples tablas legadas y aplicar lógica de negocio para generar un reporte de alto valor (una cuenta corriente) que es fundamental para la gestión.

### 4. Web Scraping Robusto (`/consultas` - SISA)

*   **Punto Clave:** El sistema se conecta a servicios externos que no tienen API, de forma resiliente.
*   **Proceso Clave:**
    1.  **Automatización:** Controla Chrome en modo **headless** (sin interfaz gráfica).
    2.  **Manejo de Tiempos:** Usa `WebDriverWait` en lugar de `time.sleep()`. Esto es más robusto porque espera a que los elementos aparezcan, no un tiempo fijo.
    3.  **Extracción:** Una vez cargada la página, pasa el HTML a `BeautifulSoup` para extraer la tabla de forma estructurada.
    4.  **Robustez:** Todo está envuelto en un `try...except...finally`. El bloque `finally` asegura que el navegador (`driver.quit()`) **siempre se cierre**, incluso si hay un error, para no dejar procesos colgados.
*   **Demuestra:** Capacidad de interactuar con el mundo exterior y superar la falta de APIs.

---

### Cierre Final

**"En resumen, el proyecto demuestra un enfoque integral: desde la integración con sistemas heredados y la migración de datos, hasta la creación de nuevos flujos de trabajo interactivos y la generación de reportes complejos, todo con un enfoque en la robustez y la entrega de valor real al usuario."**