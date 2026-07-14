# Mi radar de mercado

Dashboard personal y automático con una lectura muy concreta para cada activo:

- hasta 10 años de cierres diarios;
- precio y EMA 200;
- distancia porcentual del precio actual a su promedio simple;
- barra verde si está por encima y roja si está por debajo.

El promedio se usa para el cálculo, pero no se dibuja en el gráfico. El resultado es un sitio estático: Python solo trabaja durante la actualización y GitHub Pages sirve el HTML terminado.

## Publicarlo por primera vez

No necesitas instalar Python en tu computadora si vas a usar GitHub.

1. Crea un repositorio nuevo en GitHub.
2. Sube todos los archivos de esta carpeta a la rama `main`.
3. En el repositorio abre **Settings → Pages**.
4. En **Build and deployment → Source**, elige **GitHub Actions**.
5. Abre **Actions → Actualizar dashboard → Run workflow** y confirma.
6. Cuando termine, GitHub mostrará la dirección de tu dashboard en **Settings → Pages**.

La actualización se ejecutará todos los días a las 10:15 UTC (06:15 en Bolivia). También puedes usar **Run workflow** cuando quieras actualizarlo manualmente.

## Cambiar los activos

Solo edita [`configuracion.json`](configuracion.json). Cada activo tiene tres datos:

```json
{ "ticker": "VOO", "nombre": "S&P 500", "color": "#f1eee5" }
```

- `ticker`: el símbolo usado por Yahoo Finance.
- `nombre`: el texto que verás en la tarjeta.
- `color`: el color de su línea, en formato hexadecimal.

Puedes borrar una línea, cambiarla o agregar otra dentro de la lista `activos`. Cuida que cada elemento, salvo el último, termine en coma.

En el mismo archivo puedes cambiar el título, los años de historia, el período de la EMA y los niveles que clasifican la distancia como cercana, moderada o muy alejada.

## Probarlo en Windows (opcional)

Si deseas generar una copia local, instala Python 3.11 y ejecuta en PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python generar_dashboard.py
```

Después abre `index.html` con tu navegador. El archivo está ignorado por Git porque GitHub lo vuelve a generar en cada actualización.

## Cómo leerlo

La distancia es:

```text
(precio actual - promedio de cierres) / promedio de cierres × 100
```

La clasificación usa el valor absoluto: cuanto mayor sea la distancia, más estirado está el precio respecto de su propia historia. Es una medida descriptiva, no una recomendación de inversión.
