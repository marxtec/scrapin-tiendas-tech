"""Coolbox (VTEX IO): Selenium, porque el tercer precio de la tarjeta solo aparece en la página.

Si Chrome no logra leer una categoría, se usa la API pública de VTEX como respaldo
(trae lo mismo salvo ese tercer precio).
"""

from bs4 import BeautifulSoup

from . import vtex
from .base import a_numero, fila, log, pausa

TIENDA = "coolbox"
SELENIUM_DE_RESPALDO = False
URL_BASE = "https://www.coolbox.pe"
TARJETA = "div.coolboxpe-store-search-0-x-galleryItem"

CATEGORIAS = {
    "televisores": "tv-y-video/televisores",
    "celulares": "celulares-y-accesorios/celulares",
    "laptops": "computo/laptops",
}


def buscar_texto(tarjeta, clase):
    nodo = tarjeta.select_one(f'[class*="{clase}"]')
    return nodo.get_text("", strip=True) if nodo else None


def leer_pagina(html, categoria):
    filas = []
    for p in BeautifulSoup(html, "html.parser").select(TARJETA):
        try:
            enlace = p.find("a", href=True)
            if enlace is None:
                continue
            href = "/" + enlace["href"].replace(URL_BASE, "").lstrip("/")
            filas.append(fila(
                TIENDA, categoria,
                sku=href.strip("/").split("/")[0],
                titulo=buscar_texto(p, "productNameContainer"),
                marca=buscar_texto(p, "productBrandName"),
                vendedor=buscar_texto(p, "currentSellerName"),
                precio_referencia=a_numero(buscar_texto(p, "listPriceValue")),
                precio_oferta=a_numero(buscar_texto(p, "sellingPriceValue")),
                precio_tarjeta=a_numero(buscar_texto(p, "badgePriceContainer")),
                url=URL_BASE + href,
            ))
        except Exception as error:
            log.debug("producto saltado: %s", error)
    return filas


def con_chrome(cliente, categoria, ruta, max_paginas):
    vistos = {}
    for pagina in range(1, (max_paginas or 200) + 1):
        filas = []
        for intento in range(3):
            html = cliente.html_chrome(
                f"{URL_BASE}/{ruta}?order=OrderByPriceASC&page={pagina}",
                espera_css=TARJETA + " a[href]",
                timeout=30 + 15 * intento,
            )
            filas = leer_pagina(html, categoria)
            if filas:
                break
        nuevos = [f for f in filas if f["sku"] not in vistos]
        if not nuevos:
            break
        for f in nuevos:
            vistos[f["sku"]] = f
        log.info("%s %s: %s productos (llevamos %s)", categoria, pagina, len(filas), len(vistos))
        pausa()
    return list(vistos.values())


def capturar(cliente, categoria, ruta, max_paginas=None):
    try:
        filas = con_chrome(cliente, categoria, ruta, max_paginas)
    except Exception as error:
        log.warning("Chrome falló en %s: %s", categoria, error)
        filas = []

    # si Chrome trajo bastante menos que la API, se completa con la API
    total = vtex.total_de(
        cliente,
        f"{URL_BASE}/api/catalog_system/pub/products/search/{ruta}?_from=0&_to=0&fq=isAvailablePerSalesChannel_1:1",
    ) or 0
    if max_paginas is None and len(filas) < 0.9 * total:
        log.warning("%s: Chrome trajo %s de %s, se completa con la API", categoria, len(filas), total)
        vistos = {f["sku"]: f for f in filas}
        for f in vtex.capturar(cliente, TIENDA, categoria, URL_BASE, ruta, sku_desde="linkText"):
            vistos.setdefault(f["sku"], f)
        filas = list(vistos.values())
    return filas
