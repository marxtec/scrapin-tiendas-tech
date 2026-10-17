"""Lectura de listados Magento (Efe y Hiraoka): los precios vienen como atributos en el HTML."""

from .base import a_numero, log, pausa


def precio(tarjeta, tipo):
    """finalPrice = oferta, oldPrice = referencia."""
    nodo = tarjeta.find("span", attrs={"data-price-type": tipo})
    return a_numero(nodo.get("data-price-amount")) if nodo else None


def recorrer(cliente, url, leer_pagina, categoria, por_pagina=None, max_paginas=None):
    """Pide páginas ordenadas por precio hasta que una no traiga productos nuevos."""
    vistos = {}
    limite = f"&product_list_limit={por_pagina}" if por_pagina else ""
    for pagina in range(1, (max_paginas or 300) + 1):
        sopa = cliente.sopa(f"{url}?product_list_order=price&product_list_dir=asc{limite}&p={pagina}")
        filas = leer_pagina(sopa, categoria)
        nuevos = [f for f in filas if f["sku"] and f["sku"] not in vistos]
        if not nuevos:
            break
        for f in nuevos:
            vistos[f["sku"]] = f
        log.info("%s %s: %s productos (llevamos %s)", categoria, pagina, len(filas), len(vistos))
        pausa()
    return list(vistos.values())
