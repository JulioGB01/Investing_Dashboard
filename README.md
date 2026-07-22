# Investing Dashboard

> Dashboard estático que resume la posición de una lista configurable de activos respecto de su precio histórico y de la EMA 200.

El proyecto genera una página HTML lista para publicar. Python se ejecuta únicamente durante la actualización; GitHub Pages sirve el resultado estático. Es una herramienta personal de investigación y visualización, no un sistema de ejecución de órdenes.

## Qué muestra

- Hasta diez años de cierres diarios por activo.
- Precio reciente y media móvil exponencial de 200 períodos.
- Distancia porcentual entre el precio y su promedio de cierres.
- Lectura visual de la posición relativa de cada activo.
- Historial y configuración completamente reproducibles.

## Configuración

Edita [`configuracion.json`](configuracion.json) para definir título, años de historia, período de EMA, umbrales de clasificación y lista de activos, ticker, nombre y color.

Los símbolos se consultan a través de Yahoo Finance. Comprueba siempre la disponibilidad, exactitud y términos de uso de los datos antes de depender de una actualización.

## Actualización automática

El workflow [`update_dashboard.yml`](.github/workflows/update_dashboard.yml) genera y publica el sitio en GitHub Pages en cada cambio a `main`, manualmente desde la pestaña **Actions** y cada día a las **10:15 UTC**. El HTML generado se publica como artefacto de Pages y no se guarda en el repositorio.

## Ejecución local

Requiere Python 3.11 o compatible:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python generar_dashboard.py
```

Abre el `index.html` generado en tu navegador.

## Estructura

```text
.
├── configuracion.json                 # Activos y parámetros visibles
├── generar_dashboard.py                # Generador del sitio estático
├── requirements.txt                    # Dependencias de generación
├── .github/workflows/update_dashboard.yml
└── README.md
```

## Aviso financiero

Los gráficos y clasificaciones son descriptivos. No constituyen asesoramiento financiero, una recomendación de compra o venta, ni una garantía de resultados. Toda decisión de inversión debe considerar objetivos, riesgo, liquidez, costos y asesoramiento profesional independiente.

## Contribuciones

Consulta [`CONTRIBUTING.md`](CONTRIBUTING.md) antes de abrir un issue o pull request.