"""Construye el archivo de referencias de un sector y lo guarda.

    python -m herramientas.construir_benchmark 4711.00 2024 "Comercio al por menor"

Tarda: son dos consultas al portal por empresa. Un sector de 150 empresas son
unos pocos minutos. Se corre UNA vez por sector y por anio; la aplicacion solo
lee el archivo que queda, y nunca toca internet.
"""

from __future__ import annotations

import pathlib
import sys

from herramientas.supersociedades import descargar_sector, guardar
from herramientas.supersociedades import traer_del_portal as traer

REFERENCIAS = pathlib.Path(__file__).resolve().parents[2] / "referencias"


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    ciiu, anio = argv[1], int(argv[2])
    nombre = argv[3] if len(argv) > 3 else ""
    tope = int(argv[4]) if len(argv) > 4 else None

    def avisar(i, total, razon):
        print(f"  [{i:>3}/{total}] {razon[:52]}", flush=True)

    print(f"Sector {ciiu}, corte {anio}. Consultando el portal…", flush=True)
    sector = descargar_sector(ciiu, anio, traer, nombre=nombre, tope=tope, avisar=avisar)

    print(f"\nEmpresas con estados en Supersociedades: {sector.empresas_consultadas}")
    print(f"Empresas que aportaron algun indicador:  {sector.empresas_usadas}\n")
    print(f"{'INDICADOR':28} {'P25':>10} {'MEDIANA':>10} {'P75':>10} {'n':>5}")
    for c, r in sector.referencias.items():
        print(f"{c:28} {r.p25:10.2f} {r.mediana:10.2f} {r.p75:10.2f} {r.empresas:5}")

    ruta = guardar(sector, REFERENCIAS)
    print(f"\nGuardado en {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
