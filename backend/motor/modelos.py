"""Estructuras de datos compartidas por el motor de diagnostico financiero."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Indicador:
    """Un indicador calculado, con toda su trazabilidad.

    Cada indicador carga su propia formula, los insumos que uso y la fuente
    bibliografica. Eso alimenta el "modo docente": el usuario puede auditar
    de donde salio cada numero sin salir de la aplicacion.
    """

    codigo: str
    nombre: str
    categoria: str
    valores: list[float | None]
    unidad: str = "veces"
    formula: str = ""
    insumos: list[str] = field(default_factory=list)
    fuente: str = ""
    nota: str = ""

    @property
    def disponible(self) -> bool:
        return any(v is not None for v in self.valores)

    def variacion(self) -> float | None:
        """Diferencia entre el ultimo periodo y el primero."""
        if len(self.valores) < 2:
            return None
        ini, fin = self.valores[0], self.valores[-1]
        if ini is None or fin is None:
            return None
        return fin - ini


@dataclass
class Hallazgo:
    """Un problema detectado en los datos de entrada, antes de calcular nada."""

    severidad: str  # "error" | "advertencia" | "info"
    codigo: str
    mensaje: str
    detalle: str = ""


@dataclass
class Alerta:
    """Una senal de diagnostico derivada de los indicadores ya calculados."""

    prioridad: int
    titulo: str
    explicacion: str
    evidencia: list[str] = field(default_factory=list)
    cuentas: list[str] = field(default_factory=list)


class EstadosFinancieros:
    """Envoltura sobre los datos de entrada.

    Acepta cualquier conjunto de cuentas: si un caso futuro trae cuentas nuevas,
    no hay que tocar esta clase. Las cuentas ausentes devuelven None en vez de
    reventar, para que el motor pueda reportar "dato no disponible".
    """

    def __init__(self, datos: dict):
        self.empresa: str = datos.get("empresa", "Sin nombre")
        self.moneda: str = datos.get("moneda", "COP")
        self.unidad: str = datos.get("unidad", "unidades")
        self.periodos: list[str] = list(datos["periodos"])
        self.balance: dict[str, list] = datos.get("balance", {})
        self.resultados: dict[str, list] = datos.get("resultados", {})
        self.supuestos: dict = datos.get("supuestos", {})
        self._verificar_longitudes()

    # ---------------------------------------------------------------- carga

    @classmethod
    def desde_json(cls, ruta: str | Path) -> "EstadosFinancieros":
        with open(ruta, encoding="utf-8") as fh:
            return cls(json.load(fh))

    def _verificar_longitudes(self) -> None:
        n = len(self.periodos)
        for grupo, cuentas in (("balance", self.balance), ("resultados", self.resultados)):
            for nombre, valores in cuentas.items():
                if len(valores) != n:
                    raise ValueError(
                        f"La cuenta '{nombre}' de {grupo} tiene {len(valores)} valores "
                        f"pero se declararon {n} periodos."
                    )

    # ------------------------------------------------------------- consulta

    @property
    def n_periodos(self) -> int:
        return len(self.periodos)

    def cuenta(self, nombre: str) -> list[float | None]:
        """Serie completa de una cuenta. Lista de None si no existe."""
        if nombre in self.balance:
            return list(self.balance[nombre])
        if nombre in self.resultados:
            return list(self.resultados[nombre])
        return [None] * self.n_periodos

    def valor(self, nombre: str, i: int) -> float | None:
        return self.cuenta(nombre)[i]

    def existe(self, *nombres: str) -> bool:
        """True solo si todas las cuentas pedidas estan presentes."""
        return all(n in self.balance or n in self.resultados for n in nombres)

    # ------------------------------------------------- cuentas derivadas

    def pasivo_total(self, i: int) -> float | None:
        """Pasivo corriente + pasivo no corriente.

        Si el caso no trae un 'pasivo_total' explicito, se arma con las
        cuentas no corrientes disponibles.
        """
        explicito = self.valor("pasivo_total", i)
        if explicito is not None:
            return explicito
        pc = self.valor("pasivo_corriente", i)
        if pc is None:
            return None
        no_corriente = 0.0
        for nombre in ("pasivo_no_corriente", "deuda_financiera_lp", "otros_pasivos_lp"):
            v = self.valor(nombre, i)
            if v is not None:
                no_corriente += v
        return pc + no_corriente

    def deuda_financiera(self, i: int) -> float | None:
        partes = [
            self.valor("deuda_financiera_cp", i),
            self.valor("deuda_financiera_lp", i),
        ]
        presentes = [p for p in partes if p is not None]
        return sum(presentes) if presentes else None
