"""Ripley: las tarjetas vienen en el HTML; el vendedor sale de __NEXT_DATA__."""

from .base import a_numero, fila, log, next_data, pausa

TIENDA = "ripley"
SELENIUM_DE_RESPALDO = False  # Ripley bloquea Chrome headless

CATEGORIAS = {
    "televisores": "https://simple.ripley.com.pe/tecnologia/tv-y-cine-en-casa/televisores",
    "celulares": "https://simple.ripley.com.pe/tecnologia/celulares/celulares-y-smartphones",
    "laptops": "https://simple.ripley.com.pe/tecnologia/computacion/laptops",
    "refrigeradoras": "https://simple.ripley.com.pe/electrohogar/refrigeracion/refrigeradoras",
    "lavadoras": "https://simple.ripley.com.pe/electrohogar/lavado/lavadoras",
}


def vendedores(sopa):
    datos = next_data(sopa)
    try:
        lista = datos["props"]["pageProps"]["findabilityProps"]["data"]["products"]
    except (TypeError, KeyError):
        return {}
    resultado = {}
    for p in lista or []:
        codigo = str(p.get("parentProductID", "")).lower()
        tienda = p.get("shop") or {}
        if p.get("seller") == "RIPLEY" or not tienda:
            resultado[codigo] = "Ripley"
        else:
            resultado[codigo] = tienda.get("shopName")
    return resultado


def texto(nodo):
    return nodo.get_text(" ", strip=True) if nodo else None


def precio(tarjeta, clase):
    nodo = tarjeta.find("span", class_=clase)
    return a_numero(nodo.get_text(strip=True)) if nodo else None


def leer_pagina(sopa, categoria):
    por_sku = vendedores(sopa)
    filas = []
    for p in sopa.find_all("a", class_="product-link"):
        try:
            href = p.get("href")
            if not href:
                continue
            url = "https://simple.ripley.com.pe" + href.split("?")[0]
            sku = url.split("-")[-1]
            filas.append(fila(
                TIENDA, categoria,
                sku=sku,
                titulo=texto(p.find("p", class_="product-item--name")),
                marca=texto(p.find("span", class_="product-item--brand")),
                vendedor=por_sku.get(sku),
                precio_referencia=precio(p, "product-price-old-price"),
                precio_oferta=precio(p, "product-price-price"),
                precio_tarjeta=precio(p, "product-price-ripley-price"),
                url=url,
            ))
        except Exception as error:
            log.debug("producto saltado: %s", error)
    return filas


def capturar(cliente, categoria, url, max_paginas=None):
    vistos = {}
    for pagina in range(1, (max_paginas or 300) + 1):
        filas = leer_pagina(cliente.sopa(f"{url}?orderBy=price_asc&page={pagina}"), categoria)
        nuevos = [f for f in filas if f["sku"] not in vistos]
        if not nuevos:
            break
        for f in nuevos:
            vistos[f["sku"]] = f
        log.info("%s %s: %s productos (llevamos %s)", categoria, pagina, len(filas), len(vistos))
        pausa()
    return list(vistos.values())
