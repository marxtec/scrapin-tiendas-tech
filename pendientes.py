"""Decide qué tiendas correr y lo imprime como lista JSON (para la matriz de GitHub Actions).

    python pendientes.py todas                 -> todas
    python pendientes.py "falabella efe"       -> esas
    python pendientes.py todas --solo-faltantes -> las que hoy no tienen una captura completa
"""

import argparse
import csv
import json
from pathlib import Path

from tiendas import TIENDAS
from tiendas.base import ahora


def completa_hoy(tienda, datos):
    resumen = datos / tienda / "resumen.csv"
    if not resumen.exists():
        return False
    hoy = ahora().strftime("%Y-%m-%d")
    ok = set()
    with resumen.open(encoding="utf-8") as archivo:
        for r in csv.DictReader(archivo):
            if r["fecha_hora"].startswith(hoy) and r["estado"] in ("ok", "alerta"):
                ok.add(r["categoria"])
    return ok >= set(TIENDAS[tienda].CATEGORIAS)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tiendas", nargs="?", default="todas")
    parser.add_argument("--solo-faltantes", action="store_true")
    parser.add_argument("--datos", type=Path, default=Path("data"))
    args = parser.parse_args()

    pedidas = args.tiendas.replace(",", " ").split()
    nombres = list(TIENDAS) if pedidas in ([], ["todas"]) else [n for n in pedidas if n in TIENDAS]
    if args.solo_faltantes:
        nombres = [n for n in nombres if not completa_hoy(n, args.datos)]
    print(json.dumps(nombres))


if __name__ == "__main__":
    main()
