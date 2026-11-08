"""Pruebas automáticas de Radar IA que NO necesitan llamar a Gemini.

Cubren catálogo, persistencia, duplicados, archivo dañado, filtros,
validación de entrada y coherencia del análisis. Los casos que dependen
del modelo (ironía, mixto, inyección...) se prueban a mano: ver PRUEBAS.md.

Ejecutar desde la carpeta radar_ia:
    python -m pytest -v
"""

import json

import pytest

import analisis
import almacenamiento as alm
from analisis import AnalisisOpinion, ErrorAnalisis, ErrorEntrada


# ---------------------------------------------------------------------------
# Datos de apoyo
# ---------------------------------------------------------------------------
HERRAMIENTA = {"id": "h001", "nombre": "ChatGPT", "empresa": "OpenAI", "tipo": "asistente"}


def analisis_valido(sentimiento="positivo"):
    return AnalisisOpinion(es_pertinente=True, sentimiento=sentimiento, razon="La opinión elogia la herramienta.")


def nuevo_registro(sentimiento="positivo", herramienta=HERRAMIENTA, id_registro=None):
    return alm.crear_registro(herramienta, "Texto de prueba", analisis_valido(sentimiento), "modelo-prueba", "1.0", id_registro)


@pytest.fixture
def ruta(tmp_path):
    """Archivo de opiniones en una carpeta temporal: nunca toca datos/opiniones.json."""
    return tmp_path / "opiniones.json"


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------
def test_catalogo_real_es_valido():
    herramientas = alm.cargar_herramientas(alm.RUTA_HERRAMIENTAS)
    assert len(herramientas) >= 20
    assert len({h["id"] for h in herramientas}) == len(herramientas)


def test_catalogo_con_id_repetido_falla(tmp_path):
    ruta_catalogo = tmp_path / "herramientas.json"
    ruta_catalogo.write_text(json.dumps({"version": 1, "herramientas": [HERRAMIENTA, HERRAMIENTA]}), encoding="utf-8")
    with pytest.raises(alm.ErrorAlmacenamiento, match="ID repetido"):
        alm.cargar_herramientas(ruta_catalogo)


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------
def test_archivo_inexistente_devuelve_estructura_vacia(ruta):
    assert alm.cargar_opiniones(ruta) == {"version": 1, "opiniones": []}


def test_persistencia_guardar_y_volver_a_leer(ruta):
    registro = nuevo_registro()
    assert alm.guardar_opinion(ruta, registro) is True
    # "Reiniciar la app" = volver a leer el archivo desde cero
    assert alm.cargar_opiniones(ruta)["opiniones"] == [registro]


def test_mismo_envio_no_se_duplica(ruta):
    registro = nuevo_registro()
    alm.guardar_opinion(ruta, registro)
    assert alm.guardar_opinion(ruta, registro) is False  # reintento / reejecución
    assert len(alm.cargar_opiniones(ruta)["opiniones"]) == 1


def test_dos_opiniones_independientes(ruta):
    alm.guardar_opinion(ruta, nuevo_registro())
    alm.guardar_opinion(ruta, nuevo_registro())  # mismo texto, otro envío → otro UUID
    assert len(alm.cargar_opiniones(ruta)["opiniones"]) == 2


def test_archivo_danado_se_conserva(ruta):
    ruta.write_text('{"version": 1, "opiniones": [', encoding="utf-8")
    contenido_antes = ruta.read_text(encoding="utf-8")
    with pytest.raises(alm.ErrorAlmacenamiento):
        alm.guardar_opinion(ruta, nuevo_registro())
    assert ruta.read_text(encoding="utf-8") == contenido_antes


def test_esquema_inesperado_falla(ruta):
    ruta.write_text("[]", encoding="utf-8")  # JSON válido, pero no es el diccionario esperado
    with pytest.raises(alm.ErrorAlmacenamiento, match="esquema inesperado"):
        alm.cargar_opiniones(ruta)


def test_no_quedan_temporales(ruta):
    alm.guardar_opinion(ruta, nuevo_registro())
    assert list(ruta.parent.glob(".opiniones_*.tmp")) == []


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
def test_filtros_y_recuentos_usan_los_mismos_datos():
    otra = {"id": "h002", "nombre": "Claude", "empresa": "Anthropic", "tipo": "asistente"}
    registros = [nuevo_registro("positivo"), nuevo_registro("mixto"), nuevo_registro("positivo", otra)]

    solo_chatgpt = alm.consultar_opiniones(registros, herramienta_id="h001")
    assert len(solo_chatgpt) == 2
    assert alm.contar_por_sentimiento(solo_chatgpt) == {"positivo": 1, "negativo": 0, "neutro": 0, "mixto": 1}
    assert len(alm.consultar_opiniones(registros, sentimiento="positivo")) == 2
    assert alm.consultar_opiniones(registros, herramienta_id="h001", sentimiento="negativo") == []


# ---------------------------------------------------------------------------
# Entrada y análisis (sin llamar al modelo real)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("texto", ["", "     ", "ok", "x" * 1001])
def test_entrada_invalida_no_llama_al_modelo(monkeypatch, texto):
    def modelo_prohibido():
        raise AssertionError("¡Se llamó al modelo con una entrada inválida!")

    monkeypatch.setattr(analisis, "_crear_cadena", modelo_prohibido)
    with pytest.raises(ErrorEntrada):
        analisis.analizar_opinion(HERRAMIENTA, texto)


def test_fallo_de_api_no_se_convierte_en_neutro(monkeypatch):
    class CadenaQueFalla:
        def invoke(self, _datos):
            raise ConnectionError("sin conexión")

    monkeypatch.setattr(analisis, "_crear_cadena", lambda: CadenaQueFalla())
    with pytest.raises(ErrorAnalisis, match="No se pudo clasificar"):
        analisis.analizar_opinion(HERRAMIENTA, "Una opinión válida")


@pytest.mark.parametrize("es_pertinente, sentimiento", [(True, None), (False, "mixto")])
def test_respuesta_incoherente_se_rechaza(es_pertinente, sentimiento):
    with pytest.raises(ErrorAnalisis, match="incoherente"):
        analisis.validar_coherencia(
            AnalisisOpinion(es_pertinente=es_pertinente, sentimiento=sentimiento, razon="razón")
        )


def test_categoria_inventada_se_rechaza():
    with pytest.raises(ValueError):
        AnalisisOpinion(es_pertinente=True, sentimiento="feliz", razon="razón")


def test_fallo_de_escritura_conserva_el_original(ruta, monkeypatch):
    alm.guardar_opinion(ruta, nuevo_registro())
    contenido_antes = ruta.read_text(encoding="utf-8")

    def replace_sin_permiso(*_args):
        raise PermissionError("Permiso denegado (simulado)")

    monkeypatch.setattr(alm.os, "replace", replace_sin_permiso)
    with pytest.raises(alm.ErrorAlmacenamiento, match="No se pudo escribir"):
        alm.guardar_opinion(ruta, nuevo_registro())

    assert ruta.read_text(encoding="utf-8") == contenido_antes   # el original intacto
    assert list(ruta.parent.glob(".opiniones_*.tmp")) == []       # sin temporales sueltos
