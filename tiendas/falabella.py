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


def leer_pagina(cliente, url, orden, pagina, categoria, intentos=3):
    """Lee una página; si viene sin __NEXT_DATA__ (página de error o de espera) la reintenta."""
    for intento in range(1, intentos + 1):
        sopa = cliente.sopa(f"{url}?sortBy={ORDEN[orden]}&page={pagina}")
        datos = next_data(sopa)
        if datos is not None:
            break
        log.warning("%s %s %s: sin __NEXT_DATA__ (intento %s)", categoria, orden, pagina, intento)
        pausa(5 * intento, 10 * intento)
    else:
        raise ValueError(f"la página {pagina} ({orden}) no trae __NEXT_DATA__")
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


FALLAS_SEGUIDAS_MAX = 5  # páginas seguidas que fallan = bloqueo o caída: se corta la categoría


def recorrer(cliente, url, orden, paginas, categoria, vistos, total):
    """Recorre `paginas` páginas en un orden. Una página que falla se salta (queda en el log);
    varias seguidas cortan la categoría. Para cuando ya se tienen todos los productos."""
    fallas_seguidas = 0
    for pagina in range(1, paginas + 1):
        try:
            filas, conteo = leer_pagina(cliente, url, orden, pagina, categoria)
        except Exception as error:
            fallas_seguidas += 1
            log.warning("%s %s %s: se salta la página (%s)", categoria, orden, pagina, error)
            if fallas_seguidas >= FALLAS_SEGUIDAS_MAX:
                raise RuntimeError(f"{fallas_seguidas} páginas seguidas fallaron en {orden}") from error
            continue
        fallas_seguidas = 0
        total = total or conteo
        if not filas:
            break
        for f in filas:
            vistos.setdefault(f["sku"], f)
        log.info("%s %s %s: %s productos (llevamos %s de %s)", categoria, orden, pagina, len(filas), len(vistos), total)
        if total and (len(vistos) >= total or pagina >= math.ceil(total / 48)):
            break
        pausa()
    return total


def capturar(cliente, categoria, url, max_paginas=None):
    """Recorre de menor a mayor precio y luego de mayor a menor.

    El orden por precio no es estable entre peticiones: los productos con el mismo precio
    cambian de página y unos salen dos veces y otros ninguna (probado el 01/11/2026 en
    lavadoras: solo ascendente 96,6 % del total, ascendente + descendente 99,8 %). El
    recorrido descendente recupera los que faltan y además cubre la cola de productos caros
    que no entra en las 200 páginas que deja ver Falabella.
    """
    vistos = {}
    limite = min(max_paginas or MAX_PAGINAS_FALABELLA, MAX_PAGINAS_FALABELLA)
    total = recorrer(cliente, url, "asc", limite, categoria, vistos, None)
    cliente.esperado = total

    if max_paginas is None and total and len(vistos) < total:
        paginas_desc = min(math.ceil(total / 48), MAX_PAGINAS_FALABELLA)
        recorrer(cliente, url, "desc", paginas_desc, categoria, vistos, total)
        log.info("%s: %s de %s tras el recorrido descendente", categoria, len(vistos), total)

    return list(vistos.values())
