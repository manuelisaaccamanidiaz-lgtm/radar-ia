"""Interfaz de Radar IA con Streamlit.

Este archivo solo se ocupa de la pantalla: muestra controles, recibe la
opinión y llama a `analisis` (clasificar) y `almacenamiento` (guardar/consultar).

Ejecutar con:  streamlit run app.py
"""

import json
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from almacenamiento import (
    RUTA_HERRAMIENTAS,
    RUTA_OPINIONES,
    ErrorAlmacenamiento,
    cargar_herramientas,
    cargar_opiniones,
    consultar_opiniones,
    contar_por_sentimiento,
    crear_registro,
    guardar_opinion,
)
from analisis import (
    LONGITUD_MAXIMA,
    VERSION_PROMPT,
    ErrorAnalisis,
    ErrorEntrada,
    analizar_opinion,
    nombre_modelo,
    validar_texto,
)

# Carga GOOGLE_API_KEY y GEMINI_MODEL desde el .env junto a este archivo.
load_dotenv(Path(__file__).resolve().parent / ".env")

SENTIMIENTOS = ["positivo", "negativo", "neutro", "mixto"]
EMOJI_SENTIMIENTO = {"positivo": "🟢", "negativo": "🔴", "neutro": "⚪", "mixto": "🟡"}
TODOS = "Todos"

st.set_page_config(page_title="Radar IA", page_icon="📡")


# ---------------------------------------------------------------------------
# Estado de la sesión (vive mientras la pestaña del navegador esté abierta)
# ---------------------------------------------------------------------------
def iniciar_estado() -> None:
    """Crea las claves de st.session_state la primera vez."""
    if "mensajes" not in st.session_state:
        # Cada mensaje: {"rol", "tipo", "texto", "herramienta_id", "herramienta_nombre"}
        st.session_state.mensajes = []
    if "registro_pendiente" not in st.session_state:
        # Registro ya analizado cuya escritura falló; se puede reintentar.
        st.session_state.registro_pendiente = None


def agregar_mensaje(rol: str, tipo: str, texto: str, herramienta: dict) -> None:
    """Añade un mensaje al historial visual, asociado a su herramienta."""
    st.session_state.mensajes.append({
        "rol": rol,              # "user" o "assistant"
        "tipo": tipo,            # "opinion", "exito", "aviso" o "error"
        "texto": texto,
        "herramienta_id": herramienta["id"],
        "herramienta_nombre": herramienta["nombre"],
    })


# ---------------------------------------------------------------------------
# Lógica de un envío
# ---------------------------------------------------------------------------
def intentar_guardar(registro: dict, herramienta: dict) -> None:
    """Escribe el registro y muestra la confirmación SOLO si la escritura funcionó."""
    try:
        escrito = guardar_opinion(RUTA_OPINIONES, registro)
    except ErrorAlmacenamiento as error:
        st.session_state.registro_pendiente = registro
        agregar_mensaje(
            "assistant", "error",
            f"**No se guardó la opinión.** {error}\n\n"
            "Tu opinión sigue arriba; corrige el problema y pulsa «Reintentar guardado».",
            herramienta,
        )
        return

    st.session_state.registro_pendiente = None
    emoji = EMOJI_SENTIMIENTO[registro["sentimiento"]]
    if escrito:
        texto = f"✅ Opinión guardada. {emoji} **{registro['sentimiento']}** — {registro['razon']}"
    else:
        texto = "ℹ️ Este envío ya estaba guardado; no se duplicó."
    agregar_mensaje("assistant", "exito", texto, herramienta)


def procesar_envio(texto: str, herramienta: dict) -> None:
    """Valida, clasifica y guarda una opinión. Cada paso puede detener el proceso."""
    # 0. La herramienta queda capturada AQUÍ: cambiar el selector después
    #    no afecta a este envío.
    # UUID del envío: identifica este registro aunque se reintente el guardado.
    id_envio = str(uuid.uuid4())

    # El texto original siempre queda visible en el historial.
    agregar_mensaje("user", "opinion", texto, herramienta)

    # 1. Entrada: si no es válida, NO se llama al modelo.
    try:
        opinion = validar_texto(texto)
    except ErrorEntrada as error:
        agregar_mensaje("assistant", "aviso", str(error), herramienta)
        return

    # 2. Clasificación: un fallo NUNCA se convierte en «neutro».
    try:
        with st.spinner("Analizando la opinión..."):
            analisis = analizar_opinion(herramienta, opinion)
        modelo = nombre_modelo()
    except ErrorAnalisis as error:
        agregar_mensaje("assistant", "error", f"**No se pudo clasificar.** {error}", herramienta)
        return

    # 3. Pertinencia: un mensaje ajeno no se guarda.
    if not analisis.es_pertinente:
        agregar_mensaje(
            "assistant", "aviso",
            f"No parece una opinión sobre {herramienta['nombre']}, así que no se guardó. "
            f"_{analisis.razon}_",
            herramienta,
        )
        return

    # 4. Registro y guardado.
    registro = crear_registro(herramienta, opinion, analisis, modelo, VERSION_PROMPT, id_registro=id_envio)
    intentar_guardar(registro, herramienta)


# ---------------------------------------------------------------------------
# Secciones de la interfaz
# ---------------------------------------------------------------------------
def mostrar_historial() -> None:
    """Dibuja los mensajes guardados en st.session_state."""
    for mensaje in st.session_state.mensajes:
        with st.chat_message(mensaje["rol"]):
            if mensaje["tipo"] == "opinion":
                st.caption(f"Sobre: {mensaje['herramienta_nombre']}")
                st.markdown(mensaje["texto"])
            elif mensaje["tipo"] == "exito":
                st.success(mensaje["texto"])
            elif mensaje["tipo"] == "aviso":
                st.warning(mensaje["texto"])
            else:
                st.error(mensaje["texto"])


def seccion_emitir(herramienta: dict, herramientas_por_id: dict) -> None:
    """Sección «Emitir opinión»: chat para enviar opiniones."""
    st.subheader("Emitir opinión")
    st.write(f"Opinando sobre **{herramienta['nombre']}** ({herramienta['empresa']}).")
    st.caption(
        "La clasificación describe lo que tú expresas, no la calidad real de la herramienta. "
        "Cada mensaje se analiza por separado."
    )

    # st.chat_input devuelve el texto SOLO en la ejecución en que se envía;
    # en las demás reejecuciones (cambiar un filtro, pulsar un botón) devuelve None.
    texto = st.chat_input(f"Escribe tu opinión (máx. {LONGITUD_MAXIMA} caracteres)")
    if texto is not None:
        procesar_envio(texto, herramienta)

    # El botón de reintento se procesa ANTES de dibujar el historial para que
    # su resultado aparezca en esta misma ejecución.
    pendiente = st.session_state.registro_pendiente
    if pendiente is not None:
        if st.button("🔁 Reintentar guardado"):
            # Reutiliza el MISMO registro (mismo UUID): aunque se pulse varias
            # veces, guardar_opinion no lo duplica.
            intentar_guardar(pendiente, herramientas_por_id[pendiente["herramienta_id"]])

    mostrar_historial()


def seccion_consultar(herramientas: list[dict], herramientas_por_id: dict) -> None:
    """Sección «Consultar opiniones»: filtros, recuentos, tabla y descarga. No usa el modelo."""
    st.subheader("Consultar opiniones")

    try:
        datos = cargar_opiniones(RUTA_OPINIONES)
    except ErrorAlmacenamiento as error:
        st.error(f"No se pueden mostrar las opiniones. {error} El archivo no se ha modificado.")
        return

    columna_1, columna_2 = st.columns(2)
    filtro_herramienta = columna_1.selectbox(
        "Herramienta",
        [TODOS] + [h["id"] for h in herramientas],
        format_func=lambda valor: valor if valor == TODOS else herramientas_por_id[valor]["nombre"],
    )
    filtro_sentimiento = columna_2.selectbox("Sentimiento", [TODOS] + SENTIMIENTOS)

    # "Todos" se traduce a None, que en consultar_opiniones significa «sin filtro».
    resultado = consultar_opiniones(
        datos["opiniones"],
        herramienta_id=None if filtro_herramienta == TODOS else filtro_herramienta,
        sentimiento=None if filtro_sentimiento == TODOS else filtro_sentimiento,
    )

    # Recuentos calculados sobre el MISMO resultado filtrado que la tabla.
    conteo = contar_por_sentimiento(resultado)
    columnas = st.columns(5)
    columnas[0].metric("Total", len(resultado))
    for columna, sentimiento in zip(columnas[1:], SENTIMIENTOS):
        columna.metric(f"{EMOJI_SENTIMIENTO[sentimiento]} {sentimiento}", conteo[sentimiento])

    if not resultado:
        st.info("No hay opiniones que coincidan con estos filtros.")
        return

    filas = [
        {
            "Fecha (UTC)": r["fecha_utc"],
            "Herramienta": r["herramienta_nombre"],
            "Opinión": r["opinion_original"],
            "Sentimiento": r["sentimiento"],
            "Razón": r["razon"],
        }
        for r in resultado
    ]
    st.dataframe(filas, hide_index=True)

    contenido = json.dumps({"version": 1, "opiniones": resultado}, ensure_ascii=False, indent=2)
    st.download_button(
        "⬇️ Descargar resultado (JSON)",
        data=contenido.encode("utf-8"),
        file_name="opiniones_filtradas.json",
        mime="application/json",
    )
    st.caption("Las cifras solo representan las opiniones registradas en esta aplicación.")


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def main() -> None:
    iniciar_estado()
    st.title("📡 Radar IA")
    st.caption("Opiniones de usuarios sobre herramientas y modelos de inteligencia artificial.")

    # Sin catálogo válido no se puede hacer nada: se muestra el error y se detiene.
    try:
        herramientas = cargar_herramientas(RUTA_HERRAMIENTAS)
    except ErrorAlmacenamiento as error:
        st.error(f"No se pudo cargar el catálogo. {error}")
        st.stop()
    herramientas_por_id = {h["id"]: h for h in herramientas}

    # --- Barra lateral ---
    with st.sidebar:
        st.header("Radar IA")
        # Se muestra «nombre (empresa)», pero el valor interno es el id.
        herramienta_id = st.selectbox(
            "Herramienta",
            [h["id"] for h in herramientas],
            format_func=lambda i: f"{herramientas_por_id[i]['nombre']} ({herramientas_por_id[i]['empresa']})",
        )
        seccion = st.radio("Sección", ["Emitir opinión", "Consultar opiniones"])
        st.divider()
        if st.button("🧹 Nueva conversación"):
            # Solo limpia la sesión; los archivos no se tocan.
            st.session_state.mensajes = []
            st.session_state.registro_pendiente = None
            st.rerun()

    if seccion == "Emitir opinión":
        seccion_emitir(herramientas_por_id[herramienta_id], herramientas_por_id)
    else:
        seccion_consultar(herramientas, herramientas_por_id)


main()
