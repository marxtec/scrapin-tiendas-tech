"""Lectura del catálogo público de VTEX (lo usan Oechsle y Coolbox).

La API devuelve 50 productos por llamada y no deja pasar del producto 2500,
así que las categorías más grandes se completan con el orden inverso.
"""

from .base import a_numero, fila, log, pausa

POR_LLAMADA = 50
TOPE_VTEX = 2500


def total_de(cliente, url):
    respuesta = cliente.get(url, headers={"Accept": "application/json"})
    rango = respuesta.headers.get("resources", "")
    try:
        return int(rango.split("/")[-1])
    except ValueError:
        return None


def vendedor_principal(item):
    sellers = item.get("sellers") or []
    for s in sellers:
        if s.get("sellerDefault"):
            return s
    for s in sellers:
        if (s.get("commertialOffer") or {}).get("Price"):
            return s
    return sellers[0] if sellers else None


def descuento_por_medio_de_pago(oferta):
    """Descuento que solo aplica pagando con cierto medio (en Oechsle, la tarjeta Oh!)."""
    for teaser in oferta.get("PromotionTeasers") or oferta.get("Teasers") or []:
        teaser = {k.replace("<", "").replace(">k__BackingField", ""): v for k, v in teaser.items()}
        condiciones = teaser.get("Conditions") or {}
        condiciones = {k.replace("<", "").replace(">k__BackingField", ""): v for k, v in condiciones.items()}
        parametros = condiciones.get("Parameters") or []
        if not any(_nombre(p) == "PaymentMethodId" for p in parametros):
            continue
        efectos = teaser.get("Effects") or {}
        efectos = {k.replace("<", "").replace(">k__BackingField", ""): v for k, v in efectos.items()}
        for p in efectos.get("Parameters") or []:
            if _nombre(p) == "PromotionalPriceTableItemsDiscount":
                return a_numero(_valor(p))
    return None


def _nombre(parametro):
    return parametro.get("Name") or parametro.get("<Name>k__BackingField")


def _valor(parametro):
    return parametro.get("Value") or parametro.get("<Value>k__BackingField")


def a_fila(tienda, categoria, producto, sku_desde, url_base, vendedor_en_minusculas, con_tarjeta):
    items = producto.get("items") or []
    if not items:
        return None
    seller = vendedor_principal(items[0])
    oferta = (seller or {}).get("commertialOffer") or {}
    precio = a_numero(oferta.get("Price"))
    lista = a_numero(oferta.get("ListPrice"))
    referencia = lista if (lista and precio and lista > precio) else None
    tarjeta = None
    if con_tarjeta and precio:
        descuento = descuento_por_medio_de_pago(oferta)
        if descuento:
            tarjeta = round(precio - descuento, 2)
    vendedor = (seller or {}).get("sellerName")
    if vendedor and vendedor_en_minusculas:
        vendedor = vendedor.lower()
    return fila(
        tienda, categoria,
        sku=producto.get(sku_desde),
        titulo=producto.get("productName"),
        marca=producto.get("brand"),
        vendedor=vendedor,
        precio_referencia=referencia,
        precio_oferta=precio,
        precio_tarjeta=tarjeta,
        url=f"{url_base}/{producto.get('linkText')}/p",
    )


def capturar(cliente, tienda, categoria, url_base, ruta, sku_desde="productId",
             vendedor_en_minusculas=False, con_tarjeta=False, solo_disponibles=True,
             max_paginas=None):
    api = f"{url_base}/api/catalog_system/pub/products/search/{ruta}"
    filtro = "&fq=isAvailablePerSalesChannel_1:1" if solo_disponibles else ""
    total = total_de(cliente, f"{api}?_from=0&_to=0{filtro}") or 0
    log.info("%s: la API reporta %s productos", categoria, total)

    vistos = {}
    llamadas = 0
    for orden in ("OrderByPriceASC", "OrderByPriceDESC"):
        if orden == "OrderByPriceDESC" and total <= TOPE_VTEX:
            break
        tope = TOPE_VTEX if orden == "OrderByPriceASC" else min(total - TOPE_VTEX + 2 * POR_LLAMADA, TOPE_VTEX)
        desde = 0
        while desde < min(tope, total):
            if max_paginas and llamadas >= max_paginas:
                return list(vistos.values())
            hasta = min(desde + POR_LLAMADA, tope) - 1
            productos = cliente.json(f"{api}?O={orden}&_from={desde}&_to={hasta}{filtro}")
            llamadas += 1
            if not productos:
                break
            for p in productos:
                try:
                    f = a_fila(tienda, categoria, p, sku_desde, url_base, vendedor_en_minusculas, con_tarjeta)
                except Exception as error:
                    log.debug("producto saltado: %s", error)
                    continue
                if f and f["sku"]:
                    vistos.setdefault(f["sku"], f)
            log.info("%s %s %s-%s: llevamos %s de %s", categoria, orden[12:].lower(), desde, hasta, len(vistos), total)
            desde += POR_LLAMADA
            pausa(0.5, 1.5)
    return list(vistos.values())
