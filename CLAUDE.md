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
| Falabella | requests + `__NEXT_DATA__` (48/página) | El HTML con requests trae 28 de 48, el JSON trae los 48. Tope de 200 páginas: lo que sobra se completa con `sortBy=derived.price.search%2Cdesc`. sku = productId; vendedor = "Por " + sellerName. ~34-40 min |
| Ripley | requests + HTML; vendedor de `__NEXT_DATA__` | **Bloquea las IP de GitHub** (403 con requests, 0 productos con Chrome). Desde la laptop funciona. |
| Oechsle | API VTEX `/api/catalog_system/pub/products/search/<ruta>` con `fq=isAvailablePerSalesChannel_1:1` | 50 por llamada, tope 2500 → resto con OrderByPriceDESC. Precio Oh! = Price − `PromotionalPriceTableItemsDiscount` del teaser con condición `PaymentMethodId`. Vendedor en minúsculas. ~5 min |
| Coolbox | Selenium (48/página) con API VTEX de respaldo si Chrome trae <90 % | El tercer precio (`badgePriceContainer`) no está en ninguna API. sku = slug. ~11 min |
| Efe | requests + HTML Magento, `product_list_limit=32` | ~9 min. **Desde el 21/10 responde 503 a GitHub** (ver estado). |
| Hiraoka | requests + HTML Magento (20/página) | Desde GitHub da 403 → el Cliente pasa a Chrome para toda la corrida. ~8 min. Claude no debe hacer peticiones a Hiraoka por su cuenta (su robots.txt bloquea a Claude); el dueño tiene autorización de la tienda y corre él. |

Todas ordenan por precio para paginación estable y deduplican por sku dentro de la categoría.

Hallazgos útiles:
- En Oechsle los productos "ajenos" (fundas, mouse, riego) están mal categorizados en el propio catálogo de la tienda (ej. mouse en `/Tecnologia/Televisores/TV Hisense/`); no son anuncios. En Efe, "refrigeradoras" incluye ~165 licuadoras. Ripley también mezcla accesorios. Se capturan tal cual; se filtran en el análisis.
- Precios de Falabella vienen como lista de strings ("1,599", "199.90"); `a_numero` toma el primero.

## Robustez

- Retry de urllib3 (5, backoff 3 s) para 429/5xx; 403 no se reintenta. Con `raise_on_status=False` la última respuesta se registra.
- Tras un 403, el Cliente sigue solo con Chrome (`solo_chrome`).
- Diagnóstico (agregado el 22/10): cada HTTP ≥ 400 y cada página donde Chrome no encuentra `ESPERA_CSS` deja en el log `título | texto visible | bytes` de lo que mostró la tienda. Sirve para saber si es bloqueo (WAF/captcha) o caída.
- Cada categoría se reintenta una vez (espera 30 s); una que falla no detiene a las demás. Estado `alerta` si trae < 60 % de la captura anterior.
- Códigos de salida de capturar.py: 0 ok, 1 alguna categoría con error/alerta, 2 cero productos.
- Workflow: un job por tienda (fail-fast false, timeout 150 min), artifact siempre, un job `guardar` que hace un solo commit con reintentos de push. `concurrency: captura`.

## Horarios (UTC; Lima = UTC-5)

- `37 10 * * *` → 05:37 Lima, captura diaria.
- `47 13 * * *` → 08:47 Lima, rescate: solo tiendas sin las 5 categorías ok hoy (`pendientes.py --solo-faltantes`).
- `23 22 1-9 11 *` → 17:23 Lima del 1 al 9 de noviembre, segunda captura por Cyber Wow (ajustar si cambian las fechas).

GitHub retrasa mucho los cron: entre el 18 y el 21/10 la captura de 05:37 arrancó realmente entre 09:00 y 12:00 Lima, y el rescate 2-3 h después. La hora real queda en `timestamp` y en el nombre del archivo.

## Estado al 21/10/2026

Productos con estado ok por día:

| tienda | 17 | 18 | 19 | 20 | 21 |
|---|---|---|---|---|---|
| falabella | 33.358 | 33.611 | 33.727 | 33.721 | 32.707 |
| oechsle | 7.820 | 7.809 | 7.831 | 7.791 | 7.875 |
| coolbox | 706 | 706 | 710 | 713 | 726 |
| hiraoka | 1.012 (dos corridas de prueba) | 510 | 500 | 497 | 501 (salió en el rescate) |
| efe | 3.492 | 3.481 | 3.467 | 3.446 | **0** |
| ripley | 0 | 0 | 0 | 0 | 0 |

- Todas las corridas salen "failure" porque Ripley siempre falla. El dueño lo aceptó: prefiere recibir el correo de fallo y correr el notebook 05 de Ripley en local. Ripley sigue en la matriz a propósito.
- 21/10: Efe devolvió 503 a todas las páginas desde GitHub (también con Chrome) en la captura y en el rescate. Desde la laptop respondía normal ese mismo día → probable bloqueo de IP de GitHub. Se recomendó correr el notebook 08 en local ese día.
- 21/10: Hiraoka falló en la primera corrida (Chrome sin productos) y salió bien en el rescate: fallo transitorio.

## Pendiente

1. Revisar los logs de Efe con el diagnóstico nuevo para ver qué página devuelve (bloqueo vs caída). Si sigue fallando 2-3 días, tratarla como Ripley (correr en local) o buscar alternativa.
2. Ripley y, si aplica, Efe: posible runner self-hosted en la laptop solo para esas tiendas (requiere la laptop prendida a la hora de la captura). Por ahora el dueño corre los notebooks a mano.
3. Confirmar fechas del Cyber Wow 2026 y ajustar el tercer cron.

## Comandos útiles

```
gh run list --limit 10
gh run view <run_id> --json jobs -q '.jobs[] | "\(.databaseId) \(.name) \(.conclusion)"'
gh api --allow-escape-sequences repos/marxtec/scrapin-tiendas-tech/actions/jobs/<job_id>/logs | grep -E " == | #### |WARNING"
gh workflow run captura.yml -f tiendas="efe hiraoka"            # corrida manual
python capturar.py efe --max-paginas 1 --salida /tmp/prueba     # prueba local corta
```

Mientras un job está en curso GitHub no entrega su log; hay que esperar a que termine.
