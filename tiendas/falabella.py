"""Falabella: el listado completo (48 por página) viene en __NEXT_DATA__, basta con requests.

Falabella solo deja ver 200 páginas. Si la categoría tiene más productos, el resto
se completa pidiendo el listado ordenado de mayor a menor precio.
"""

import math

from .base import a_numero, fila, log, next_data, pausa

TIENDA = "falabella"
SELENIUM_DE_RESPALDO = True
ESPERA_CSS = "div.grid-pod"

CATEGORIAS = {
    "televisores": "https://www.falabella.com.pe/falabella-pe/category/cat6370551/Televisores-Smart-TV",
    "celulares": "https://www.falabella.com.pe/falabella-pe/category/CATG15605/Smartphones",
    "laptops": "https://www.falabella.com.pe/falabella-pe/category/cat40712/Laptops",
    "refrigeradoras": "https://www.falabella.com.pe/falabella-pe/category/cat780530/Refrigerador",
    "lavadoras": "https://www.falabella.com.pe/falabella-pe/category/cat780522/Lavadoras",
}

MAX_PAGINAS_FALABELLA = 200
ORDEN = {"asc": "derived.price.search%2Casc", "desc": "derived.price.search%2Cdesc"}


def precio(producto, *tipos):
    for tipo in tipos:
        for p in producto.get("prices") or []:
            if p.get("type") == tipo:
                valor = a_numero(p.get("price"))
                if valor is not None:
                    return valor
    return None


def leer_pagina(cliente, url, orden, pagina, categoria):
    sopa = cliente.sopa(f"{url}?sortBy={ORDEN[orden]}&page={pagina}")
    datos = next_data(sopa)
    if datos is None:
        raise ValueError("la página no trae __NEXT_DATA__")
    props = datos.get("props", {}).get("pageProps", {})
    filas = []
    for p in props.get("results") or []:
        try:
            sku = p.get("productId")
            if not sku:
                continue
            vendedor = p.get("sellerName")
            filas.append(fila(
                TIENDA, categoria,
                sku=sku,
                titulo=p.get("displayName"),
                marca=p.get("brand"),
                vendedor=f"Por {vendedor}" if vendedor else None,
                precio_referencia=precio(p, "normalPrice"),
                precio_oferta=precio(p, "internetPrice", "eventPrice"),
                precio_tarjeta=precio(p, "cmrPrice"),
                url=f"https://www.falabella.com.pe/falabella-pe/product/{sku}",
            ))
        except Exception as error:
            log.debug("producto saltado: %s", error)
    total = (props.get("pagination") or {}).get("count")
    return filas, total


def capturar(cliente, categoria, url, max_paginas=None):
    vistos = {}
    limite = min(max_paginas or MAX_PAGINAS_FALABELLA, MAX_PAGINAS_FALABELLA)

    total = None
    for pagina in range(1, limite + 1):
        filas, conteo = leer_pagina(cliente, url, "asc", pagina, categoria)
        total = total or conteo
        if not filas:
            break
        for f in filas:
            vistos.setdefault(f["sku"], f)
        log.info("%s asc %s: %s productos (llevamos %s de %s)", categoria, pagina, len(filas), len(vistos), total)
        if total and pagina >= math.ceil(total / 48):
            break
        pausa()

    # cola de productos caros que no entra en las 200 páginas
    if max_paginas is None and total and total > MAX_PAGINAS_FALABELLA * 48:
        faltan = total - MAX_PAGINAS_FALABELLA * 48
        paginas_desc = min(math.ceil(faltan / 48) + 2, MAX_PAGINAS_FALABELLA)
        for pagina in range(1, paginas_desc + 1):
            filas, _ = leer_pagina(cliente, url, "desc", pagina, categoria)
            if not filas:
                break
            for f in filas:
                vistos.setdefault(f["sku"], f)
            log.info("%s desc %s: %s productos (llevamos %s de %s)", categoria, pagina, len(filas), len(vistos), total)
            pausa()

    return list(vistos.values())
