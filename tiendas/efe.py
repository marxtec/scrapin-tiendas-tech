"""Tiendas Efe (Magento): requests, 32 productos por página (el máximo que acepta)."""

from . import magento
from .base import fila, log

TIENDA = "efe"
SELENIUM_DE_RESPALDO = True

CATEGORIAS = {
    "televisores": "https://www.efe.com.pe/tecnologia/televisores/smart-tv.html",
    "celulares": "https://www.efe.com.pe/tecnologia/celulares/celulares-y-smartphones.html",
    "laptops": "https://www.efe.com.pe/tecnologia/computacion/laptops.html",
    "refrigeradoras": "https://www.efe.com.pe/electrohogar/refrigeracion/refrigeradoras.html",
    "lavadoras": "https://www.efe.com.pe/electrohogar/lavado/lavadoras.html",
}


def leer_pagina(sopa, categoria):
    filas = []
    for p in sopa.find_all("li", class_="product-item"):
        try:
            caja = p.find("div", class_="price-box")
            enlace = p.find("a", class_="product-item-link")
            if caja is None or enlace is None:
                continue
            marca = p.find("span", class_="brand-name")
            vendedor = p.find("div", class_="label-sold-by")
            filas.append(fila(
                TIENDA, categoria,
                sku=caja.get("data-product-id"),
                titulo=enlace.get_text(" ", strip=True),
                marca=marca.get_text(" ", strip=True) if marca else None,
                vendedor=vendedor.get_text(" ", strip=True) if vendedor else None,
                precio_referencia=magento.precio(p, "oldPrice"),
                precio_oferta=magento.precio(p, "finalPrice"),
                url=enlace.get("href"),
            ))
        except Exception as error:
            log.debug("producto saltado: %s", error)
    return filas


def capturar(cliente, categoria, url, max_paginas=None):
    return magento.recorrer(cliente, url, leer_pagina, categoria, por_pagina=32, max_paginas=max_paginas)
