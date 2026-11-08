"""Lectura, validación, guardado y consulta de los archivos JSON de Radar IA.

Este módulo NO sabe nada de Streamlit ni del modelo de IA: solo trabaja
con archivos y diccionarios. Así se puede estudiar (y probar) por separado.
"""

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Rutas construidas a partir de la ubicación de ESTE archivo, no del
# directorio desde el que se lance Streamlit.
CARPETA_PROYECTO = Path(__file__).resolve().parent
RUTA_HERRAMIENTAS = CARPETA_PROYECTO / "datos" / "herramientas.json"
RUTA_OPINIONES = CARPETA_PROYECTO / "datos" / "opiniones.json"

VERSION_ARCHIVO = 1
TIPOS_VALIDOS = {"asistente", "modelo abierto", "herramienta local", "imágenes", "programación"}
CAMPOS_HERRAMIENTA = ("id", "nombre", "empresa", "tipo")
CAMPOS_REGISTRO = (
    "id", "fecha_utc", "herramienta_id", "herramienta_nombre", "opinion_original",
    "sentimiento", "razon", "modelo", "version_prompt",
)


class ErrorAlmacenamiento(Exception):
    """Error al leer, validar o escribir un archivo de datos."""


# ---------------------------------------------------------------------------
# Lectura auxiliar
# ---------------------------------------------------------------------------
def _leer_json(ruta: Path):
    """Lee un archivo JSON y devuelve su contenido.

    Convierte los errores técnicos en ErrorAlmacenamiento con un mensaje claro.
    """
    try:
        with open(ruta, "r", encoding="utf-8") as archivo:
            return json.load(archivo)
    except json.JSONDecodeError as error:
        raise ErrorAlmacenamiento(
            f"El archivo {ruta.name} no contiene JSON válido "
            f"(línea {error.lineno}, columna {error.colno})."
        ) from error
    except OSError as error:
        raise ErrorAlmacenamiento(f"No se pudo leer {ruta.name}: {error}") from error


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------
def cargar_herramientas(ruta: Path = RUTA_HERRAMIENTAS) -> list[dict]:
    """Lee y valida el catálogo: estructura, campos obligatorios e IDs únicos."""
    if not ruta.exists():
        raise ErrorAlmacenamiento(f"No existe el catálogo {ruta.name}.")

    datos = _leer_json(ruta)

    # 1. Estructura general: {"version": 1, "herramientas": [...]}
    if not isinstance(datos, dict) or not isinstance(datos.get("herramientas"), list):
        raise ErrorAlmacenamiento("El catálogo debe ser un objeto con una lista 'herramientas'.")
    if datos.get("version") != VERSION_ARCHIVO:
        raise ErrorAlmacenamiento(f"Versión de catálogo no soportada: {datos.get('version')!r}.")

    herramientas = datos["herramientas"]
    if not herramientas:
        raise ErrorAlmacenamiento("El catálogo está vacío.")

    # 2. Cada herramienta: campos obligatorios no vacíos y tipo permitido.
    ids_vistos = set()
    for posicion, herramienta in enumerate(herramientas, start=1):
        if not isinstance(herramienta, dict):
            raise ErrorAlmacenamiento(f"El elemento {posicion} del catálogo no es un objeto.")
        for campo in CAMPOS_HERRAMIENTA:
            valor = herramienta.get(campo)
            if not isinstance(valor, str) or not valor.strip():
                raise ErrorAlmacenamiento(
                    f"El elemento {posicion} del catálogo no tiene un '{campo}' válido."
                )
        if herramienta["tipo"] not in TIPOS_VALIDOS:
            raise ErrorAlmacenamiento(
                f"Tipo desconocido en {herramienta['id']}: {herramienta['tipo']!r}."
            )

        # 3. IDs únicos: el id es la clave interna, no puede repetirse.
        if herramienta["id"] in ids_vistos:
            raise ErrorAlmacenamiento(f"ID repetido en el catálogo: {herramienta['id']}.")
        ids_vistos.add(herramienta["id"])

    return herramientas


# ---------------------------------------------------------------------------
# Opiniones
# ---------------------------------------------------------------------------
def estructura_vacia() -> dict:
    """Devuelve el diccionario inicial de opiniones."""
    return {"version": VERSION_ARCHIVO, "opiniones": []}


def cargar_opiniones(ruta: Path = RUTA_OPINIONES) -> dict:
    """Lee el diccionario persistente de opiniones.

    - Si el archivo no existe: devuelve la estructura vacía (se creará al guardar).
    - Si existe pero está dañado o tiene un esquema inesperado: lanza
      ErrorAlmacenamiento. NUNCA lo reemplaza en silencio por una lista vacía.
    """
    if not ruta.exists():
        return estructura_vacia()

    datos = _leer_json(ruta)

    if not isinstance(datos, dict) or not isinstance(datos.get("opiniones"), list):
        raise ErrorAlmacenamiento(
            f"{ruta.name} tiene un esquema inesperado: se esperaba un objeto con la lista 'opiniones'."
        )
    if datos.get("version") != VERSION_ARCHIVO:
        raise ErrorAlmacenamiento(f"Versión de {ruta.name} no soportada: {datos.get('version')!r}.")

    for posicion, registro in enumerate(datos["opiniones"], start=1):
        if not isinstance(registro, dict) or any(campo not in registro for campo in CAMPOS_REGISTRO):
            raise ErrorAlmacenamiento(
                f"El registro {posicion} de {ruta.name} no tiene todos los campos obligatorios."
            )

    return datos


def crear_registro(herramienta: dict, texto: str, analisis, modelo: str,
                   version_prompt: str, id_registro: str | None = None) -> dict:
    """Construye el registro que se guardará.

    El PROGRAMA genera el UUID, la fecha, la identidad de la herramienta y los
    metadatos. Del modelo solo se toman `sentimiento` y `razon`.

    `id_registro` permite reutilizar el UUID generado al enviar el mensaje,
    para que un reintento no cree un registro duplicado.
    """
    return {
        "id": id_registro or str(uuid.uuid4()),
        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "herramienta_id": herramienta["id"],
        "herramienta_nombre": herramienta["nombre"],
        "opinion_original": texto,
        "sentimiento": analisis.sentimiento,
        "razon": analisis.razon,
        "modelo": modelo,
        "version_prompt": version_prompt,
    }


def guardar_opinion(ruta: Path, registro: dict) -> bool:
    """Añade un registro al archivo sin perder los anteriores.

    Devuelve True si se escribió y False si ya existía un registro con ese id
    (reintento del mismo envío). Lanza ErrorAlmacenamiento si algo falla.
    """
    # 1. Leer el estado actual. Si el archivo está dañado, cargar_opiniones
    #    lanza un error y aquí se detiene todo: el archivo NO se sobrescribe.
    datos = cargar_opiniones(ruta)

    # 2. Evitar duplicados: el mismo envío (mismo UUID) solo se guarda una vez.
    if any(existente["id"] == registro["id"] for existente in datos["opiniones"]):
        return False

    # 3. Añadir en memoria.
    datos["opiniones"].append(registro)

    # 4. Escribir el diccionario completo en un archivo temporal del MISMO
    #    directorio y, si todo salió bien, reemplazar el original de una vez.
    #    Así nunca queda un opiniones.json escrito a medias.
    ruta_temporal = None
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=ruta.parent, prefix=".opiniones_", suffix=".tmp", delete=False
        ) as temporal:
            ruta_temporal = Path(temporal.name)
            json.dump(datos, temporal, ensure_ascii=False, indent=2)
            temporal.flush()
            os.fsync(temporal.fileno())  # asegura que los datos lleguen al disco
        os.replace(ruta_temporal, ruta)  # reemplazo final
    except OSError as error:
        # Si falló, se borra el temporal y el original queda intacto.
        if ruta_temporal is not None and ruta_temporal.exists():
            ruta_temporal.unlink(missing_ok=True)
        raise ErrorAlmacenamiento(f"No se pudo escribir {ruta.name}: {error}") from error

    return True


# ---------------------------------------------------------------------------
# Consultas (no llaman al modelo)
# ---------------------------------------------------------------------------
def consultar_opiniones(registros: list[dict], herramienta_id: str | None = None,
                        sentimiento: str | None = None) -> list[dict]:
    """Filtra los registros. Un filtro en None significa «Todos»."""
    resultado = []
    for registro in registros:
        if herramienta_id is not None and registro["herramienta_id"] != herramienta_id:
            continue
        if sentimiento is not None and registro["sentimiento"] != sentimiento:
            continue
        resultado.append(registro)
    return resultado


def contar_por_sentimiento(registros: list[dict]) -> dict[str, int]:
    """Cuenta cuántos registros hay de cada sentimiento."""
    conteo = {"positivo": 0, "negativo": 0, "neutro": 0, "mixto": 0}
    for registro in registros:
        if registro["sentimiento"] in conteo:
            conteo[registro["sentimiento"]] += 1
    return conteo
