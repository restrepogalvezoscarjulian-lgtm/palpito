"""Pruebas del puntaje de salud financiera.

Igual que en el resto del proyecto, cada nota se verifica contra un calculo
escrito a mano en el docstring. Aqui importa mas que en ningun otro modulo:
un puntaje que nadie puede reproducir con lapiz y papel es un puntaje que no
se puede defender en una sustentacion.

Correr con:  pytest -v
"""

from pathlib import Path

import pytest

from motor.modelos import EstadosFinancieros
from motor.salud import (
    BANDAS,
    CRITERIOS,
    ESCALA_TENDENCIA,
    PESOS_DIMENSION,
    PESO_NIVEL,
    PESO_TENDENCIA,
    banda,
    interpolar,
    puntaje_salud,
)
from motor.indicadores import calcular_todos

CASO = Path(__file__).resolve().parents[2] / "casos" / "comercial_andina.json"
TOL = 0.01


@pytest.fixture(scope="module")
def ef():
    return EstadosFinancieros.desde_json(CASO)


@pytest.fixture(scope="module")
def salud(ef):
    return puntaje_salud(ef)


def _criterio(salud, codigo):
    for d in salud["dimensiones"]:
        for c in d["criterios"]:
            if c["codigo"] == codigo:
                return c
    raise AssertionError(f"no aparece el criterio {codigo}")


# ================================================ 1. INTERPOLACION DE LA ESCALA


def test_interpolar_en_los_puntos_exactos():
    """En un punto declarado de la escala devuelve su puntaje, sin desviarse."""
    escala = ((0.5, 0), (1.0, 45), (1.5, 85), (2.0, 100))
    assert interpolar(1.0, escala) == pytest.approx(45)
    assert interpolar(2.0, escala) == pytest.approx(100)


def test_interpolar_entre_dos_puntos():
    """Punto medio entre (1,0 -> 45) y (1,5 -> 85).

    1,25 esta a la mitad del tramo, luego 45 + (85-45) x 0,5 = 65.
    """
    escala = ((0.5, 0), (1.0, 45), (1.5, 85), (2.0, 100))
    assert interpolar(1.25, escala) == pytest.approx(65, abs=TOL)


def test_interpolar_no_extrapola_fuera_de_rango():
    """Fuera de los extremos se aplana: nadie saca mas de 100 ni menos de 0."""
    escala = ((0.5, 0), (2.0, 100))
    assert interpolar(0.1, escala) == pytest.approx(0)
    assert interpolar(50.0, escala) == pytest.approx(100)


def test_escalas_declaradas_en_orden_creciente():
    """Si una escala quedara desordenada, la interpolacion mentiria en silencio."""
    for c in CRITERIOS:
        valores = [p[0] for p in c.escala]
        assert valores == sorted(valores), f"escala desordenada en {c.codigo}"
        for _, puntaje in c.escala:
            assert 0 <= puntaje <= 100


# ============================================================== 2. PONDERACIONES


def test_los_pesos_de_dimension_suman_cien():
    assert sum(PESOS_DIMENSION.values()) == pytest.approx(100)


def test_los_pesos_dentro_de_cada_dimension_suman_cien():
    for dimension in PESOS_DIMENSION:
        propios = [c.peso for c in CRITERIOS if c.dimension == dimension]
        assert propios, f"la dimension {dimension} no tiene criterios"
        assert sum(propios) == pytest.approx(100), dimension


def test_toda_dimension_declarada_tiene_criterios_y_viceversa():
    declaradas = set(PESOS_DIMENSION)
    usadas = {c.dimension for c in CRITERIOS}
    assert declaradas == usadas


def test_nivel_y_tendencia_suman_uno():
    assert PESO_NIVEL + PESO_TENDENCIA == pytest.approx(1.0)


def test_los_criterios_apuntan_a_indicadores_que_existen(ef):
    """Un codigo mal escrito dejaria el criterio fuera del puntaje sin avisar."""
    codigos = set(calcular_todos(ef))
    for c in CRITERIOS:
        if not c.derivado:
            assert c.codigo in codigos, f"{c.codigo} no existe como indicador"


# ================================================================== 3. BANDAS


def test_banda_por_puntaje():
    assert banda(92.0)["nombre"] == "Solida"
    assert banda(65.0)["nombre"] == "Aceptable con reservas"
    assert banda(45.0)["nombre"] == "Fragil"
    assert banda(12.0)["nombre"] == "Critica"


def test_bandas_cubren_toda_la_escala_sin_huecos():
    pisos = [b[0] for b in BANDAS]
    assert pisos == sorted(pisos, reverse=True)
    assert pisos[-1] == 0.0
    for p in range(0, 101):
        assert banda(float(p))["nombre"]


# ================================ 4. CALIFICACION VERIFICADA CONTRA CALCULO A MANO


def test_razon_corriente_nivel_calculado_a_mano(salud):
    """Razon corriente 2024 = 3620 / 2050 = 1,7659 veces.

    Cae en el tramo (1,5 -> 85) a (2,0 -> 100) de la escala:
        85 + (100 - 85) x (1,7659 - 1,5) / (2,0 - 1,5)
        85 + 15 x 0,5317 = 92,98
    """
    c = _criterio(salud, "razon_corriente")
    assert c["valor"] == pytest.approx(1.76585, abs=1e-4)
    assert c["nivel"] == pytest.approx(92.98, abs=TOL)


def test_la_nota_es_la_mezcla_declarada_de_nivel_y_tendencia(salud):
    """Toda nota evaluable debe reproducirse con 70% nivel + 30% tendencia."""
    for d in salud["dimensiones"]:
        for c in d["criterios"]:
            if not c["evaluable"]:
                continue
            if c["tendencia"] is None:
                assert c["nota"] == pytest.approx(c["nivel"], abs=TOL)
            else:
                esperado = PESO_NIVEL * c["nivel"] + PESO_TENDENCIA * c["tendencia"]
                assert c["nota"] == pytest.approx(esperado, abs=TOL), c["codigo"]


def test_tendencia_neutra_cuando_el_indicador_no_se_movio():
    """Un indicador identico en los dos periodos saca exactamente 50 de tendencia."""
    assert interpolar(0.0, ESCALA_TENDENCIA) == pytest.approx(50)


def test_un_solo_dato_util_no_inventa_tendencia(salud):
    """El costo implicito de la deuda no existe en el primer periodo.

    Por eso el spread ROIC solo tiene un dato util y debe calificarse solo por
    nivel, en vez de compararse consigo mismo y sacar una tendencia neutra que
    no significa nada.
    """
    c = _criterio(salud, "spread_roic")
    assert c["tendencia"] is None
    assert c["nota"] == pytest.approx(c["nivel"], abs=TOL)
    assert "no hay dos periodos comparables" in c["motivo"]


def test_ciclo_de_caja_mejora_cuando_baja():
    """En el ciclo de caja y en el endeudamiento, bajar es mejorar."""
    for codigo in ("ciclo_conversion_efectivo", "pkt", "endeudamiento_activo"):
        c = next(x for x in CRITERIOS if x.codigo == codigo)
        assert c.mejora == "baja"


# ============================================== 5. AGREGACION Y RENORMALIZACION


def test_el_puntaje_es_la_suma_de_los_aportes(salud):
    """El total tiene que cuadrar con lo que aporta cada dimension."""
    aportes = sum(d["aporte"] for d in salud["dimensiones"] if d["evaluable"])
    assert salud["puntaje"] == pytest.approx(aportes, abs=0.1)


def test_cada_dimension_es_el_promedio_ponderado_de_sus_criterios(salud):
    for d in salud["dimensiones"]:
        if not d["evaluable"]:
            continue
        vivos = [c for c in d["criterios"] if c["evaluable"]]
        pesos = sum(c["peso_en_dimension"] for c in vivos)
        esperado = sum(c["nota"] * c["peso_en_dimension"] for c in vivos) / pesos
        assert d["puntaje"] == pytest.approx(esperado, abs=TOL), d["nombre"]


def test_puntaje_dentro_del_rango(salud):
    assert 0 <= salud["puntaje"] <= 100


def test_un_dato_faltante_no_cuenta_como_cero():
    """Sin gastos financieros no hay cobertura de intereses.

    Ese criterio debe excluirse y su peso pasar al resto de la dimension, no
    arrastrar la nota a cero: "no informado" no es lo mismo que "malo".
    """
    datos = {
        "periodos": ["2023", "2024"],
        "balance": {
            "efectivo": [200, 210], "cuentas_por_cobrar": [800, 820],
            "inventarios": [900, 910], "activo_corriente": [1900, 1940],
            "propiedad_planta_equipo": [1100, 1120], "activo_total": [3000, 3060],
            "proveedores": [700, 710], "pasivo_corriente": [1000, 1010],
            "patrimonio": [1800, 1850],
        },
        "resultados": {
            "ventas": [4000, 4200], "costo_ventas": [2600, 2730],
            "utilidad_bruta": [1400, 1470], "gastos_operacionales": [900, 940],
            "utilidad_operacional": [500, 530],
            "utilidad_antes_impuestos": [500, 530],
            "impuestos": [175, 186], "utilidad_neta": [325, 344],
        },
    }
    s = puntaje_salud(EstadosFinancieros(datos))
    cobertura = _criterio(s, "cobertura_intereses")
    assert cobertura["evaluable"] is False
    assert any(e["nombre"] == cobertura["nombre"] for e in s["excluidos"])

    endeudamiento = next(d for d in s["dimensiones"] if d["nombre"] == "Endeudamiento")
    otro = _criterio(s, "endeudamiento_activo")
    # Al quedar solo, se lleva el 100% del peso de su dimension.
    assert otro["peso_efectivo"] == pytest.approx(100)
    assert endeudamiento["puntaje"] == pytest.approx(otro["nota"], abs=TOL)


def test_sin_datos_no_se_inventa_un_puntaje():
    s = puntaje_salud(EstadosFinancieros({"periodos": ["2024"]}))
    assert s["disponible"] is False
    assert "puntaje" not in s


# ================================================== 6. LA VALIDACION MANDA


def test_el_caso_descuadrado_sale_marcado_como_no_confiable(salud):
    """Comercial Andina no cuadra el balance, y el puntaje tiene que decirlo.

    El numero se calcula igual, pero llega con la advertencia encima: la
    calidad de los datos sigue siendo puerta previa a cualquier conclusion.
    """
    assert salud["disponible"] is True
    assert salud["confiable"] is False
    assert "no cuadran" in salud["advertencia"]


def test_la_metodologia_viaja_con_el_puntaje(salud):
    """El frontend tiene que poder pintar la formula al lado de la nota."""
    m = salud["metodologia"]
    assert m["peso_nivel"] == 70 and m["peso_tendencia"] == 30
    for d in salud["dimensiones"]:
        for c in d["criterios"]:
            assert c["justificacion"] and c["fuente"]
            assert len(c["escala"]) >= 2
