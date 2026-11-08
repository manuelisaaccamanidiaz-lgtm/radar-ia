"""Carga las opiniones de ejemplo del entregable usando el clasificador REAL.

El taller pide al menos 12 registros ficticios repartidos entre 4 elementos
del catálogo y las 4 categorías. Aquí hay 16 (4 herramientas × 4 categorías).

Las OPINIONES son ficticias, pero la CLASIFICACIÓN la hace Gemini con el mismo
código que usa la app (analizar_opinion + guardar_opinion). Así los registros
son evidencia real del funcionamiento, no etiquetas escritas a mano.

Ejecutar desde la carpeta radar_ia:
    python cargar_ejemplos.py

Se puede ejecutar varias veces: cada ejemplo tiene un id fijo, así que
guardar_opinion no lo duplica.
"""

import uuid
from pathlib import Path

from dotenv import load_dotenv

from almacenamiento import (
    RUTA_HERRAMIENTAS,
    RUTA_OPINIONES,
    ErrorAlmacenamiento,
    cargar_herramientas,
    crear_registro,
    guardar_opinion,
)
from analisis import VERSION_PROMPT, ErrorAnalisis, ErrorEntrada, analizar_opinion, nombre_modelo

load_dotenv(Path(__file__).resolve().parent / ".env")

# (herramienta_id, sentimiento esperado, opinión ficticia)
EJEMPLOS = [
    # ChatGPT
    ("h001", "positivo", "Sus respuestas son claras y me ahorran horas de trabajo cada semana."),
    ("h001", "negativo", "Me inventó una cita bibliográfica que no existe y casi la entrego en clase."),
    ("h001", "neutro",   "Lo uso principalmente para redactar correos y resumir documentos."),
    ("h001", "mixto",    "Explica muy bien los conceptos, pero a veces se equivoca con cálculos sencillos."),
    # Claude
    ("h002", "positivo", "Me ayudó a entender un código enorme explicándolo paso a paso, excelente."),
    ("h002", "negativo", "Sus respuestas son demasiado largas y me cuesta encontrar lo importante."),
    ("h002", "neutro",   "Es un asistente que permite adjuntar archivos y hacer preguntas sobre ellos."),
    ("h002", "mixto",    "Escribe con un estilo muy natural, aunque a veces se niega a cosas sencillas."),
    # Gemini
    ("h003", "positivo", "Integrarlo con mis documentos de Google me facilitó mucho el estudio."),
    ("h003", "negativo", "Qué gran ayuda: me dio tres respuestas distintas a la misma pregunta."),  # ironía
    ("h003", "neutro",   "Lo probé desde el celular y también desde el navegador del computador."),
    ("h003", "mixto",    "Responde muy rápido, pero sus explicaciones de programación son superficiales."),
    # Ollama
    ("h014", "positivo", "Poder correr modelos en mi propio computador sin pagar es fantástico."),
    ("h014", "negativo", "Mi portátil se puso lentísimo y los modelos grandes ni siquiera cargaron."),
    ("h014", "neutro",   "Se instala en el equipo y los modelos se descargan desde la terminal."),
    ("h014", "mixto",    "Me encanta la privacidad de trabajar local, pero consume demasiada memoria."),
]

# Espacio de nombres fijo: el mismo número de ejemplo genera SIEMPRE el mismo UUID.
NAMESPACE_EJEMPLOS = uuid.uuid5(uuid.NAMESPACE_URL, "radar-ia/ejemplos")


def main() -> None:
    herramientas = {h["id"]: h for h in cargar_herramientas(RUTA_HERRAMIENTAS)}
    modelo = nombre_modelo()

    guardados = repetidos = fallidos = coincidencias = 0
    print(f"Modelo: {modelo} | Versión del prompt: {VERSION_PROMPT}\n")

    for numero, (herramienta_id, esperado, texto) in enumerate(EJEMPLOS, start=1):
        herramienta = herramientas[herramienta_id]
        etiqueta = f"[{numero:02d}] {herramienta['nombre']:<8}"

        try:
            analisis = analizar_opinion(herramienta, texto)
        except (ErrorEntrada, ErrorAnalisis) as error:
            # Un fallo NO se guarda como "neutro": se informa y se sigue.
            fallidos += 1
            print(f"{etiqueta} ❌ no clasificado: {error}")
            continue

        if not analisis.es_pertinente:
            fallidos += 1
            print(f"{etiqueta} ⚠️  no pertinente (no se guarda): {analisis.razon}")
            continue

        id_fijo = str(uuid.uuid5(NAMESPACE_EJEMPLOS, str(numero)))
        registro = crear_registro(herramienta, texto, analisis, modelo, VERSION_PROMPT, id_registro=id_fijo)

        try:
            escrito = guardar_opinion(RUTA_OPINIONES, registro)
        except ErrorAlmacenamiento as error:
            fallidos += 1
            print(f"{etiqueta} ❌ no guardado: {error}")
            continue

        coincide = analisis.sentimiento == esperado
        coincidencias += coincide
        marca = "✅" if coincide else "🔶 DISCREPANCIA"
        estado = "guardado" if escrito else "ya existía"
        repetidos += not escrito
        guardados += escrito
        print(f"{etiqueta} {marca} esperado={esperado:<8} observado={analisis.sentimiento:<8} ({estado})")
        if not coincide:
            print(f"      razón del modelo: {analisis.razon}")

    print(
        f"\nNuevos: {guardados} | Ya existían: {repetidos} | Fallidos: {fallidos} | "
        f"Coincidencias con lo esperado: {coincidencias}/{len(EJEMPLOS)}"
    )
    print("Copia las discrepancias (🔶) a PRUEBAS.md y explícalas en la reflexión.")


if __name__ == "__main__":
    main()
