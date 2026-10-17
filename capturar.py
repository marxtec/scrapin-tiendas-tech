"""Captura de precios por tienda.

Uso:
    python capturar.py falabella ripley       # tiendas concretas
    python capturar.py todas                  # las seis
    python capturar.py efe --max-paginas 2    # prueba corta

Por cada tienda guarda data/<tienda>/<AAAA-MM-DD_HHMM>.csv.gz y agrega una fila por
categoría a data/<tienda>/resumen.csv. Una categoría que falla no detiene a las demás.

Código de salida: 0 todo bien; 1 alguna categoría falló o vino sospechosamente corta
(los datos que sí salieron igual se guardan); 2 no salió ningún producto.
"""

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

import pandas as pd

from tiendas import TIENDAS
from tiendas.base import COLUMNAS, Cliente, ahora, log

INTENTOS_POR_CATEGORIA = 2
CAIDA_SOSPECHOSA = 0.6  # menos del 60 % de la captura anterior

CAMPOS_RESUMEN = ["fecha_hora", "categoria", "productos", "anterior", "segundos", "estado", "detalle"]


def ultima_cantidad(resumen, categoria):
    if not resumen.exists():
        return None
    ultima = None
    with resumen.open(encoding="utf-8") as archivo:
        for r in csv.DictReader(archivo):
            if r["categoria"] == categoria and r["estado"] in ("ok", "alerta") and r["productos"].isdigit():
                ultima = int(r["productos"])
    return ultima


def capturar_categoria(modulo, cliente, categoria, url, max_paginas):
    error = None
    for intento in range(1, INTENTOS_POR_CATEGORIA + 1):
        try:
            filas = modulo.capturar(cliente, categoria, url, max_paginas=max_paginas)
            if filas:
                return filas, None
            error = "0 productos"
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        log.warning("%s/%s intento %s falló: %s", modulo.TIENDA, categoria, intento, error)
        cliente.reiniciar_driver()
        time.sleep(30 * intento)
    return [], error


def capturar_tienda(nombre, salida, max_paginas=None, solo=None):
    modulo = TIENDAS[nombre]
    carpeta = salida / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    resumen = carpeta / "resumen.csv"
    marca = ahora().strftime("%Y-%m-%d_%H%M")

    cliente = Cliente(selenium_de_respaldo=modulo.SELENIUM_DE_RESPALDO)
    tablas, filas_resumen, problemas = [], [], 0
    try:
        for categoria, url in modulo.CATEGORIAS.items():
            if solo and categoria not in solo:
                continue
            inicio = time.time()
            filas, error = capturar_categoria(modulo, cliente, categoria, url, max_paginas)
            segundos = round(time.time() - inicio)
            anterior = ultima_cantidad(resumen, categoria)

            if error:
                estado, detalle = "error", error[:300]
                problemas += 1
            elif max_paginas is None and anterior and len(filas) < CAIDA_SOSPECHOSA * anterior:
                estado, detalle = "alerta", f"cayó de {anterior} a {len(filas)}"
                problemas += 1
            else:
                estado, detalle = "ok", ""

            log.info("== %s/%s: %s productos en %ss (%s)", nombre, categoria, len(filas), segundos, estado)
            if filas:
                tablas.append(pd.DataFrame(filas, columns=COLUMNAS))
            filas_resumen.append({
                "fecha_hora": marca, "categoria": categoria, "productos": len(filas),
                "anterior": anterior or "", "segundos": segundos, "estado": estado, "detalle": detalle,
            })
    finally:
        cliente.cerrar()

    total = 0
    if tablas:
        df = pd.concat(tablas, ignore_index=True).drop_duplicates(["categoria", "sku"])
        total = len(df)
        if max_paginas is None:
            df.to_csv(carpeta / f"{marca}.csv.gz", index=False, compression="gzip")
        else:
            df.to_csv(carpeta / f"prueba_{marca}.csv", index=False)

    # las pruebas cortas no ensucian el historial
    if max_paginas is None:
        nuevo = not resumen.exists()
        with resumen.open("a", newline="", encoding="utf-8") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=CAMPOS_RESUMEN)
            if nuevo:
                escritor.writeheader()
            escritor.writerows(filas_resumen)

    log.info("#### %s: %s productos, %s categorías con problemas", nombre, total, problemas)
    return total, problemas


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tiendas", nargs="+", help="nombres de tienda o 'todas'")
    parser.add_argument("--max-paginas", type=int, default=None, help="tope de páginas por categoría (prueba)")
    parser.add_argument("--categorias", nargs="*", default=None, help="solo estas categorías")
    parser.add_argument("--salida", type=Path, default=Path("data"))
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)

    nombres = list(TIENDAS) if args.tiendas == ["todas"] else args.tiendas
    desconocidas = [n for n in nombres if n not in TIENDAS]
    if desconocidas:
        parser.error(f"tiendas desconocidas: {desconocidas}. Opciones: {list(TIENDAS)}")

    total, problemas = 0, 0
    for nombre in nombres:
        try:
            t, p = capturar_tienda(nombre, args.salida, args.max_paginas, args.categorias)
        except Exception:
            log.exception("la tienda %s falló por completo", nombre)
            t, p = 0, 1
        total += t
        problemas += p

    if total == 0:
        sys.exit(2)
    sys.exit(1 if problemas else 0)


if __name__ == "__main__":
    main()
