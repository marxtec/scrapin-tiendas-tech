"""Hiraoka (Magento): requests, 20 productos por página."""

from . import magento
from .base import fila, log

TIENDA = "hiraoka"
SELENIUM_DE_RESPALDO = True  # desde GitHub requests recibe 403
ESPERA_CSS = ".product-item .price-box"

CATEGORIAS = {
    "televisores": "https://hiraoka.com.pe/televisores/televisores",
    "celulares": "https://hiraoka.com.pe/celulares-y-telefonia/celulares/smartphones",
    "laptops": "https://hiraoka.com.pe/computo-y-tablets/computadoras/laptops",
    "refrigeradoras": "https://hiraoka.com.pe/electrohogar/refrigeracion/refrigeradoras",
    "lavadoras": "https://hiraoka.com.pe/electrohogar/lavado-y-limpieza/lavadoras",
}


def leer_pagina(sopa, categoria):
    filas = []
    for p in sopa.find_all(class_="product-item"):
        try:
            # dos enlaces: el primero es la marca y el último el título completo
            enlaces = p.find_all("a", class_="product-item-link")
            caja = p.find(class_="price-box")
            if not enlaces or caja is None:
                continue
            filas.append(fila(
                TIENDA, categoria,
                sku=caja.get("data-product-id"),
                titulo=enlaces[-1].get_text(" ", strip=True),
                marca=enlaces[0].get_text(" ", strip=True),
                vendedor="Hiraoka",
                precio_referencia=magento.precio(p, "oldPrice"),
                precio_oferta=magento.precio(p, "finalPrice"),
                url=enlaces[-1].get("href"),
            ))
        except Exception as error:
            log.debug("producto saltado: %s", error)
    return filas


def capturar(cliente, categoria, url, max_paginas=None):
    return magento.recorrer(cliente, url, leer_pagina, categoria, max_paginas=max_paginas)
