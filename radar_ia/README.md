# 📡 Radar IA

Chatbot en Streamlit para registrar opiniones de usuarios sobre herramientas y modelos de inteligencia artificial, analizar su sentimiento con LangChain + Gemini y consultarlas después de reiniciar la aplicación.

Es una adaptación autorizada del taller *«Percepción de futbolistas mediante un chatbot»* (Tribuna Global): el catálogo de futbolistas se sustituye por uno de herramientas de IA.

> La clasificación describe lo que **expresa el usuario**, no la calidad real de la herramienta. Las cifras solo representan las opiniones registradas en esta aplicación. El catálogo es una selección didáctica, no un ranking.

## Estructura

```text
radar_ia/
├── app.py               # Interfaz (Streamlit)
├── analisis.py          # Prompt, modelo y clasificación
├── almacenamiento.py    # Archivos JSON y consultas
├── datos/
│   ├── herramientas.json   # Catálogo (20 herramientas, h001…h020)
│   └── opiniones.json      # Opiniones persistidas
├── requirements.txt
├── .env.example
├── .gitignore
├── cargar_ejemplos.py   # Carga las 16 opiniones de ejemplo con el clasificador real
├── test_radar.py        # Pruebas automáticas (sin llamar al modelo)
├── README.md
└── PRUEBAS.md           # Registro de pruebas de aceptación
```

## Instalación (Dev Container, carpeta `/app`)

```bash
cd /app/radar_ia          # o la ruta donde esté esta carpeta dentro del contenedor
pip install -r requirements.txt
```

## Configuración del `.env`

```bash
cp .env.example .env
```

Edita `.env` y reemplaza los marcadores:

| Variable | Qué poner |
| --- | --- |
| `GOOGLE_API_KEY` | Tu clave de Google AI Studio. |
| `GEMINI_MODEL` | El nombre de un modelo Gemini compatible con salida estructurada (por ejemplo, el que ya probaste). |

`.env` está en `.gitignore`: **nunca** lo subas al repositorio. El código no contiene claves ni nombres de modelo; los lee de estas variables.

## Ejecución

```bash
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

Abre `http://localhost:8501` en el navegador del equipo anfitrión (VS Code suele reenviar el puerto automáticamente).

## Opiniones de ejemplo (entregable: mínimo 12 registros)

```bash
python cargar_ejemplos.py
```

Envía 16 opiniones **ficticias** (ChatGPT, Claude, Gemini y Ollama × las 4 categorías) por el **mismo** flujo de la app: `analizar_opinion` → `crear_registro` → `guardar_opinion`. La clasificación la hace Gemini, no está escrita a mano. Cada ejemplo tiene un UUID fijo, así que ejecutarlo dos veces no duplica registros. Las discrepancias (🔶) entre lo esperado y lo observado se copian a `PRUEBAS.md`.

## Pruebas automáticas

```bash
python -m pytest -v
```

`test_radar.py` comprueba sin usar la API: catálogo e IDs únicos, persistencia tras releer el archivo, no duplicación por reintento, opiniones independientes, archivo dañado conservado, esquema inesperado, filtros y recuentos, entrada inválida que no llama al modelo, fallo de API que no se convierte en «neutro» y coherencia pertinencia/sentimiento. Usa carpetas temporales: **no** modifica `datos/opiniones.json`.

## Lista de entregables

- [ ] `streamlit run app.py` funciona.
- [ ] Catálogo con 20 herramientas (`datos/herramientas.json`).
- [ ] `datos/opiniones.json` con ≥ 12 registros (`python cargar_ejemplos.py`).
- [ ] Versiones confirmadas con `pip show` (tabla de arriba).
- [ ] Capturas: opinión guardada → app reiniciada → la consulta filtrada la recupera.
- [ ] `PRUEBAS.md` con resultado observado de los 16 casos.
- [ ] Reflexión sobre dos errores o ambigüedades de clasificación.

## Versiones utilizadas

Obtenidas con `pip show` en Python 3.12 tras instalar `requirements.txt`:

| Librería | Versión |
| --- | --- |
| Python | 3.12.10 |
| streamlit | 1.67.0 |
| langchain-core | 1.7.6 |
| langchain-google-genai | 4.4.3 |
| python-dotenv | 1.2.4 |
| pydantic | 2.14.3 |

Si en tu Dev Container obtienes otras versiones, compruébalas con:

```bash
pip show streamlit langchain-core langchain-google-genai python-dotenv pydantic | grep -E "^(Name|Version)"
```

## Decisiones técnicas

- **Proveedor:** `langchain-google-genai` (`ChatGoogleGenerativeAI`) en lugar de `langchain-openai`.
- **Salida estructurada:** `with_structured_output(AnalisisOpinion, method="json_schema")`. Según la referencia oficial de `ChatGoogleGenerativeAI.with_structured_output`, `json_schema` es el método nativo recomendado (y el predeterminado); `function_calling` es menos fiable y `json_mode` está obsoleto.
- **Temperatura 0:** reduce la variación, pero no garantiza exactitud ni determinismo.
- **Coherencia:** el esquema Pydantic no comprueba la relación entre `es_pertinente` y `sentimiento`; `validar_coherencia()` en `analisis.py` lo hace en código. Si la respuesta es incoherente, se trata como un error y no se guarda.
- **Duplicados:** cada envío recibe un UUID al enviarse. Ese UUID es el `id` del registro y `guardar_opinion` no escribe un id que ya exista; por eso «Reintentar guardado» puede pulsarse varias veces sin duplicar.
- **Escritura segura:** archivo temporal en `datos/` + `os.replace`. Evita archivos a medio escribir, pero no resuelve el acceso concurrente de varios usuarios.

## Notas y dudas sobre el catálogo

Los nombres y empresas son los indicados en el enunciado. Algunas clasificaciones de `tipo` son discutibles y conviene revisarlas:

- **DeepSeek (h009)** y **Qwen (h012):** marcados como `modelo abierto` porque publican pesos de sus modelos, aunque también tienen una aplicación de chat (podrían ser `asistente`).
- **Kimi (h013):** marcado como `asistente` (la app de chat), aunque Moonshot AI también publica modelos con pesos abiertos.
- **Llama (h006):** `modelo abierto` en el sentido de «pesos descargables»; su licencia tiene restricciones y no es software libre en sentido estricto.
- **Stable Diffusion (h019):** marcado como `imágenes`, aunque también es un modelo abierto.
- **NotebookLM (h015)** y **Perplexity (h011):** marcados como `asistente`; no hay una categoría de «investigación» o «búsqueda» en la lista.
- **GitHub Copilot (h005):** GitHub pertenece a Microsoft; se mantiene «GitHub» como empresa, tal como indica el enunciado.
