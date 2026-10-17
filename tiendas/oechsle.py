"""Oechsle (VTEX): se lee el catálogo por la API pública, sin Selenium.

El precio con tarjeta Oh! viene como una promoción condicionada al medio de pago.
"""

from . import vtex

TIENDA = "oechsle"
SELENIUM_DE_RESPALDO = False
URL_BASE = "https://www.oechsle.pe"

CATEGORIAS = {
    "televisores": "tecnologia/televisores",
    "celulares": "tecnologia/telefonia/celulares",
    "laptops": "tecnologia/computo/laptops",
    "refrigeradoras": "electrohogar/refrigeracion/refrigeradoras",
    "lavadoras": "electrohogar/lavado/lavadoras",
}


def capturar(cliente, categoria, ruta, max_paginas=None):
    return vtex.capturar(
        cliente, TIENDA, categoria, URL_BASE, ruta,
        sku_desde="productId",
        vendedor_en_minusculas=True,
        con_tarjeta=True,
        max_paginas=max_paginas,
    )
