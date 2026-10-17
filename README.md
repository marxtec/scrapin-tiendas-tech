# scrapin-tiendas-tech

Captura diaria y automática de precios de televisores, celulares, laptops, refrigeradoras y lavadoras en seis tiendas online de Lima: Falabella, Ripley, Oechsle, Coolbox, Tiendas Efe y Hiraoka.

Corre solo en GitHub Actions y guarda un CSV comprimido por tienda y captura en `data/`.

## Datos

```
data/<tienda>/<AAAA-MM-DD_HHMM>.csv.gz   una fila por producto (hora de Lima)
data/<tienda>/resumen.csv                una fila por categoría y captura: productos, segundos, estado
```

Columnas de cada CSV:

| columna | descripción |
|---|---|
| tienda | falabella, ripley, oechsle, coolbox, efe, hiraoka |
| sku | código del producto en la tienda (estable entre días) |
| titulo, marca, vendedor | como aparecen en la tienda |
| categoria | televisores, celulares, laptops, refrigeradoras, lavadoras |
| precio_referencia | precio tachado (vacío si no hay) |
| precio_oferta | precio de venta |
| precio_tarjeta | precio con tarjeta de la tienda: CMR, Ripley, Oh! o el tercer precio de Coolbox |
| url | enlace al producto |
| timestamp | fecha y hora de Lima |

Lectura:

```python
import pandas as pd
df = pd.read_csv("data/falabella/2026-10-17_0537.csv.gz", dtype={"sku": str})
```

Si en un día hay dos capturas (la de rescate o la segunda del Cyber Wow), usar `timestamp` para quedarse con la que corresponda.

## Cómo se captura cada tienda

| tienda | método | por qué |
|---|---|---|
| Falabella | requests + JSON `__NEXT_DATA__` de la página | el HTML solo trae 28 de 48 productos, pero el JSON de la página trae los 48. Falabella corta en 200 páginas: lo que falta se completa pidiendo el orden inverso |
| Ripley | requests + HTML, vendedor desde `__NEXT_DATA__` | bloquea Chrome headless |
| Oechsle | API pública de catálogo VTEX | más rápida y completa que el navegador; el precio Oh! viene como promoción por medio de pago |
| Coolbox | Selenium, con la API VTEX de respaldo | el tercer precio solo aparece en la página ya cargada |
| Efe | requests + HTML Magento, 32 por página | los precios vienen como atributos |
| Hiraoka | requests + HTML Magento, 20 por página | igual que Efe |

Todas piden los listados ordenados por precio, para que la paginación sea estable.

## Robustez

- Reintentos con espera creciente ante errores de red, 403, 429 y 5xx, respetando `Retry-After`.
- Timeouts en cada petición. Chrome con carga `eager`, espera a que el número de productos deje de cambiar y se reinicia si se cae.
- Una categoría que falla se reintenta una vez y no detiene a las demás. Lo que sí salió se guarda igual.
- Un producto con datos raros se salta sin romper la página.
- Deduplicado por `sku` dentro de cada categoría.
- Alerta si una categoría trae menos del 60 % de lo que trajo la captura anterior (posible bloqueo o cambio en la web). Queda marcada como `alerta` en `resumen.csv` y el job sale en rojo.
- En GitHub cada tienda corre en su propio job: si una se cae, las otras siguen. Los datos se suben aunque el job falle y se guardan todos en un solo commit al final, con reintentos de push.

## Horarios

En UTC dentro de `.github/workflows/captura.yml` (Lima = UTC-5):

| cron | Lima | qué hace |
|---|---|---|
| `37 10 * * *` | 05:37 | captura diaria de las seis tiendas |
| `47 13 * * *` | 08:47 | rescate: vuelve a correr solo las tiendas que hoy no tienen captura completa |
| `23 22 1-9 11 *` | 17:23, 1 al 9 de noviembre | segunda captura diaria por el Cyber Wow |

Se usan minutos "raros" porque en el minuto 00 de cada hora la cola de GitHub está más cargada y los cron se retrasan o se saltan. La madrugada además es tráfico bajo en las tiendas y los precios del día ya están puestos. Si cambian las fechas del Cyber Wow, editar la tercera línea.

Duración aproximada por tienda: Falabella 35-45 min, Ripley ~15 min, Efe ~8 min, Oechsle ~7 min, Coolbox ~8 min, Hiraoka ~3 min. Corren en paralelo.

## Correr a mano

En GitHub: pestaña Actions → "Captura de precios" → Run workflow. Se puede elegir tiendas (`falabella efe`) y un tope de páginas para probar (con tope no se guarda historial).

En local:

```
pip install -r requirements.txt
python capturar.py todas
python capturar.py falabella ripley
python capturar.py efe --max-paginas 2           # prueba corta, guarda data/efe/prueba_*.csv
python capturar.py oechsle --categorias lavadoras
```

Coolbox necesita Chrome instalado.

## Puesta en marcha

1. Crear el repo en GitHub y subir esta carpeta.
2. Settings → Actions → General → Workflow permissions: "Read and write permissions" (para que el bot pueda hacer commit de los datos).
3. Correr una vez a mano desde Actions para comprobar que todas las tiendas responden desde los servidores de GitHub.

Notas:

- GitHub desactiva los cron de un repo sin actividad por 60 días. Los commits diarios de datos lo mantienen activo.
- Si una tienda bloquea las IP de GitHub, su job saldrá en rojo con `error` en `resumen.csv`. En ese caso hay que correr esa tienda desde una máquina propia.
- Algunas tiendas mezclan productos que no son de la categoría (accesorios, licuadoras en refrigeradoras de Efe, fundas en televisores de Oechsle). Se capturan tal cual porque así los clasifica la tienda; hay que filtrarlos en el análisis.
