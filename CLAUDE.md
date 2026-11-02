# CLAUDE.md

Repo de captura automática de precios (GitHub Actions) para el proyecto "Validador de ofertas" del curso Analítica de la Web (UP 2026-II).

- GitHub: https://github.com/marxtec/scrapin-tiendas-tech (público desde el 17/10/2026, para tener minutos de Actions ilimitados).
- Repo hermano: `../validador_ofertas` es el repo "académico" que se sustenta ante el docente (notebooks simples, informe, propuesta). **Este repo no lleva nada del informe**: solo scraping, optimizado y robusto. No hace falta que el código parezca de estudiante.
- Los notebooks de `../validador_ofertas/notebooks` (03 Falabella, 05 Ripley, 06 Oechsle, 07 Coolbox, 08 Efe, 09 Hiraoka) son la referencia de la lógica. Este repo debe producir las mismas columnas y el mismo formato de `sku` para poder unir historiales. No modificar esos notebooks desde aquí.
- Commits con el correo noreply `217266901+marxtec@users.noreply.github.com` (configurado en `.git/config` local). No usar el correo personal: el repo es público.

## Estructura

```
capturar.py            CLI: python capturar.py <tiendas|todas> [--max-paginas N] [--categorias ...]
pendientes.py          decide qué tiendas corre el workflow (todas / elegidas / solo faltantes de hoy)
tiendas/base.py        Cliente (requests con reintentos + Chrome de respaldo), fila(), a_numero(), resumen_html()
tiendas/vtex.py        API pública de catálogo VTEX (Oechsle y Coolbox)
tiendas/magento.py     listados Magento (Efe e Hiraoka)
tiendas/<tienda>.py    CATEGORIAS, SELENIUM_DE_RESPALDO, ESPERA_CSS y capturar()
.github/workflows/captura.yml
data/<tienda>/<AAAA-MM-DD_HHMM>.csv.gz   (hora de Lima)
data/<tienda>/resumen.csv                una fila por categoría y corrida: productos, anterior, segundos, estado, detalle
```

Columnas: tienda, sku, titulo, marca, vendedor, categoria, precio_referencia, precio_oferta, precio_tarjeta, url, timestamp.

## Método por tienda (validado contra los CSV de los notebooks)

| tienda | método | notas |
|---|---|---|
| Falabella | requests + `__NEXT_DATA__` (48/página) | El HTML con requests trae 28 de 48, el JSON trae los 48. Dos recorridos: ascendente y descendente por precio (ver hallazgos). Tope de 200 páginas por orden. sku = productId; vendedor = "Por " + sellerName. ~85 min desde el 02/11 (antes ~40) |
| Ripley | requests + HTML; vendedor de `__NEXT_DATA__` | **Bloquea las IP de GitHub** (403 con requests, 0 productos con Chrome). Desde la laptop funciona: el dueño corre el notebook 05 a mano. |
| Oechsle | API VTEX `/api/catalog_system/pub/products/search/<ruta>` con `fq=isAvailablePerSalesChannel_1:1` | 50 por llamada, tope 2500 → resto con OrderByPriceDESC. Precio Oh! = Price − `PromotionalPriceTableItemsDiscount` del teaser con condición `PaymentMethodId`. Vendedor en minúsculas. ~5 min |
| Coolbox | Selenium (48/página) con API VTEX de respaldo si Chrome trae <90 % | El tercer precio (`badgePriceContainer`) no está en ninguna API. sku = slug. ~11 min |
| Efe | requests + HTML Magento, `product_list_limit=32` | ~9 min. **Bloquea las IP de GitHub desde el 30/10**: `426 Blocked` / `Error 54113` del CDN (Varnish), también con Chrome. Desde la laptop funciona: el dueño corre el notebook 08 a mano. |
| Hiraoka | requests + HTML Magento (20/página) | **Corre automática en GitHub** y funciona todos los días (~7 min, ~500 productos). requests recibe 403 (`Error 54113`, el mismo CDN que bloquea a Efe) → el Cliente pasa a Chrome y así entra. Riesgo: si endurecen el bloqueo como en Efe, caería igual. Claude no hace peticiones directas a hiraoka.com.pe (su robots.txt bloquea a Claude): se revisa por los logs de Actions y `data/hiraoka/`. |

Todas ordenan por precio y deduplican por sku dentro de la categoría. Magento (Efe/Hiraoka) y Coolbox paran en la primera página incompleta (es la última) en vez de pedir una vacía.

Hallazgos útiles:
- **El orden por precio no es estable entre peticiones** (productos con el mismo precio cambian de página). En Falabella, solo ascendente traía 94-96 % del total que reporta la tienda (ej. 01/11 televisores 11.027 de 11.768) y el chequeo contra la corrida anterior no lo detectaba. Prueba del 01/11 en lavadoras: ascendente 96,6 %, ascendente + descendente 99,8 %. Desde el 02/11 se hacen los dos recorridos (el descendente para cuando ya están todos).
- En Oechsle los productos "ajenos" (fundas, mouse, riego) están mal categorizados en el propio catálogo de la tienda (ej. mouse en `/Tecnologia/Televisores/TV Hisense/`); no son anuncios. En Efe, "refrigeradoras" incluye ~165 licuadoras. Ripley también mezcla accesorios. Se capturan tal cual; se filtran en el análisis.
- Precios de Falabella vienen como lista de strings ("1,599", "199.90"); `a_numero` toma el primero.

## Robustez

- Retry de urllib3 (5, backoff 3 s) para 429/5xx; 403 no se reintenta. Con `raise_on_status=False` la última respuesta se registra.
- Tras un 403, el Cliente sigue solo con Chrome (`solo_chrome`).
- Diagnóstico (agregado el 22/10): cada HTTP ≥ 400 y cada página donde Chrome no encuentra `ESPERA_CSS` deja en el log `título | texto visible | bytes` de lo que mostró la tienda. Sirve para saber si es bloqueo (WAF/captcha) o caída.
- Cada categoría se reintenta una vez (espera 30 s); una que falla no detiene a las demás.
- Falabella: una página sin `__NEXT_DATA__` se reintenta 3 veces; si sigue fallando se salta y se sigue (5 seguidas cortan la categoría), en vez de perder la categoría entera.
- Estado `alerta` (datos guardados igual, job en rojo) si: trae < 80 % de la captura anterior; trae < 90 % del total que reporta la tienda (`cliente.esperado`, lo llenan Falabella, Oechsle y Coolbox); > 10 % sin precio de oferta; > 5 % sin título. Calibrado con 17/10-01/11: peor caída normal 13 %, peor categoría 4 % sin precio (Efe celulares).
- Códigos de salida de capturar.py: 0 ok, 1 alguna categoría con error/alerta, 2 cero productos.
- Workflow: un job por tienda (fail-fast false, timeout 240 min por el doble recorrido de Falabella), artifact siempre, un job `guardar` que hace un solo commit con reintentos de push. `concurrency: captura`.

## Horarios (UTC; Lima = UTC-5)

- `37 10 * * *` → 05:37 Lima, captura diaria.
- `47 13 * * *` → 08:47 Lima, rescate: solo tiendas sin las 5 categorías ok hoy (`pendientes.py --solo-faltantes`).
- `23 22 1-9 11 *` → 17:23 Lima del 1 al 9 de noviembre, segunda captura por Cyber Wow. Fechas oficiales confirmadas: Cyber Wow del 2 al 5/11/2026 (00:00-23:59); el 1 y del 6 al 9 quedan como base de comparación.

GitHub retrasa mucho los cron: entre el 18 y el 21/10 la captura de 05:37 arrancó realmente entre 09:00 y 12:00 Lima, y el rescate 2-3 h después; el 01/11 la de 05:37 arrancó 11:53 y la de 17:23 a las 20:36. La hora real queda en `timestamp` y en el nombre del archivo.

## Estado al 01/11/2026

Cobertura diaria combinando GitHub (`data/`) y los CSV manuales de `../validador_ofertas/notebooks`:

- **Falabella, Oechsle, Coolbox, Hiraoka** (GitHub): todos los días del 17/10 al 01/11 con todas sus categorías ok. Coolbox tiene 3 categorías a propósito (no vende refrigeradoras ni lavadoras).
- **Efe**: GitHub ok del 17/10 al 29/10 salvo el 21/10; el 21/10 y del 30/10 en adelante, notebook 08 manual (`efe_AAAA-MM-DD.csv`). Sin huecos desde el 16/10.
- **Ripley**: solo manual (notebook 05). Faltan el **20/10 y el 27/10** (no existen en ningún lado, verificado el 01/11) y el 31/10 vino **sin celulares**.
- Primer día con las 6 tiendas completas: **17/10** (el 16/10 hay 5, falta Falabella).

Decisiones del dueño:
- Ripley y Efe siguen en la matriz de GitHub aunque fallen siempre: el correo de "failure" le sirve de recordatorio y las corre a mano. **No automatizarlas en la laptop** (lo pidió explícitamente el 01/11).
- Desde el 28/10, Ripley tiene ~1.300 laptops del vendedor de marketplace "UNALUKA INTERNACIONAL": son reales, no un error; conviene separar marketplace en el análisis.

## Pendiente

1. Primera corrida con el doble recorrido de Falabella (02/11): confirmar que llega a ~99 % del total en todas las categorías y que dura < 2 h.
2. Vigilar Hiraoka: mismo CDN que bloqueó a Efe.

## Comandos útiles

```
gh run list --limit 10
gh run view <run_id> --json jobs -q '.jobs[] | "\(.databaseId) \(.name) \(.conclusion)"'
gh api --allow-escape-sequences repos/marxtec/scrapin-tiendas-tech/actions/jobs/<job_id>/logs | grep -E " == | #### |WARNING"
gh workflow run captura.yml -f tiendas="efe hiraoka"            # corrida manual
python capturar.py efe --max-paginas 1 --salida /tmp/prueba     # prueba local corta
```

Mientras un job está en curso GitHub no entrega su log; hay que esperar a que termine.
