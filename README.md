# 📡 Radar IA

Chatbot en Streamlit para registrar opiniones de usuarios sobre herramientas y modelos de inteligencia artificial, analizar su sentimiento con LangChain + Gemini y consultarlas después de reiniciar la aplicación.

Es una adaptación autorizada del taller *«Percepción de futbolistas mediante un chatbot»* (Tribuna Global): el catálogo de futbolistas se sustituye por uno de herramientas de IA.

> La clasificación describe lo que **expresa el usuario**, no la calidad real de la herramienta. Las cifras solo representan las opiniones registradas en esta aplicación. El catálogo es una selección didáctica, no un ranking.

## Estructura

```text
.
├── .devcontainer/
│   └── devcontainer.json    # Configuración del Dev Container de VS Code
├── .vscode/
│   └── tasks.json           # Tareas: Streamlit, pytest y opiniones de ejemplo
├── Dockerfile               # Imagen de Python 3.12 con las dependencias
├── docker-compose.yml       # Monta el proyecto en /app y publica el puerto 8501
├── .dockerignore
├── .gitignore
├── README.md
└── radar_ia/                # Código de la aplicación
    ├── app.py               # Interfaz (Streamlit)
    ├── analisis.py          # Prompt, modelo y clasificación
    ├── almacenamiento.py    # Archivos JSON y consultas
    ├── datos/
    │   ├── herramientas.json   # Catálogo (20 herramientas, h001…h020)
    │   └── opiniones.json      # Opiniones persistidas
    ├── cargar_ejemplos.py   # Carga las 16 opiniones de ejemplo con el clasificador real
    ├── test_radar.py        # Pruebas automáticas (sin llamar al modelo)
    ├── PRUEBAS.md           # Registro de pruebas de aceptación y reflexión
    ├── requirements.txt
    ├── .env.example
    └── .gitignore
```

## Instalación (Dev Container)

Requisitos: Docker Desktop y VS Code con la extensión **Dev Containers**.

1. Abre esta carpeta en VS Code.
2. `Ctrl + Shift + P` → **Dev Containers: Reopen in Container**. Al crearse, el contenedor instala `radar_ia/requirements.txt` automáticamente.
3. En la terminal del contenedor:

```bash
cd /app/radar_ia
```

> Si el puerto 8501 está ocupado por otro contenedor, deténlo primero (`docker stop <nombre>`).

## Configuración del `.env`

```bash
cp .env.example .env
```

Edita `radar_ia/.env` y reemplaza los marcadores:

| Variable | Qué poner |
| --- | --- |
| `GOOGLE_API_KEY` | Tu clave de Google AI Studio. |
| `GEMINI_MODEL` | El nombre de un modelo Gemini compatible con salida estructurada (en las pruebas se usó `gemini-3.5-flash-lite`). |

`.env` está en `.gitignore`: **nunca** se sube al repositorio. El código no contiene claves ni nombres de modelo; los lee de estas variables.

## Ejecución

Desde `radar_ia/` (o con `Ctrl + Shift + B` en VS Code):

```bash
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

Abre `http://localhost:8501` en el navegador.

## Opiniones de ejemplo

```bash
python cargar_ejemplos.py
```

Envía 16 opiniones **ficticias** (ChatGPT, Claude, Gemini y Ollama × las 4 categorías) por el **mismo** flujo de la app: `analizar_opinion` → `crear_registro` → `guardar_opinion`. La clasificación la hace Gemini, no está escrita a mano. Cada ejemplo tiene un UUID fijo, así que ejecutarlo dos veces no duplica registros.

## Pruebas automáticas

```bash
python -m pytest -v
```

`test_radar.py` comprueba sin usar la API: catálogo e IDs únicos, persistencia tras releer el archivo, no duplicación por reintento, opiniones independientes, archivo dañado conservado, fallo de escritura, esquema inesperado, filtros y recuentos, entrada inválida que no llama al modelo, fallo de API que no se convierte en «neutro» y coherencia pertinencia/sentimiento. Usa carpetas temporales: **no** modifica `datos/opiniones.json`.

Los resultados de las 16 pruebas de aceptación y la reflexión están en [`radar_ia/PRUEBAS.md`](radar_ia/PRUEBAS.md).

## Entregables

- [x] Aplicación ejecutable con `streamlit run app.py`.
- [x] Catálogo con 20 herramientas ([`radar_ia/datos/herramientas.json`](radar_ia/datos/herramientas.json)).
- [x] Opiniones persistidas: ≥ 12 registros entre 4 herramientas y 4 categorías ([`radar_ia/datos/opiniones.json`](radar_ia/datos/opiniones.json)).
- [x] Registro de pruebas y reflexión ([`radar_ia/PRUEBAS.md`](radar_ia/PRUEBAS.md)).
- [ ] Versiones confirmadas con `pip show`.
- [ ] Capturas de persistencia tras reinicio y consulta filtrada.

## Versiones utilizadas

Python 3.12 en el Dev Container, tras instalar `radar_ia/requirements.txt`:

| Librería | Versión |
| --- | --- |
| Python | 3.12.10 |
| streamlit | 1.67.0 |
| langchain-core | 1.7.6 |
| langchain-google-genai | 4.4.3 |
| python-dotenv | 1.2.4 |
| pydantic | 2.14.3 |
| pytest | 9.2.0 |

Para comprobarlas:

```bash
pip show streamlit langchain-core langchain-google-genai python-dotenv pydantic pytest | grep -E "^(Name|Version)"
```

## Decisiones técnicas

- **Proveedor:** `langchain-google-genai` (`ChatGoogleGenerativeAI`) en lugar de `langchain-openai`.
- **Salida estructurada:** `with_structured_output(AnalisisOpinion, method="json_schema")`. Según la referencia oficial de `ChatGoogleGenerativeAI.with_structured_output`, `json_schema` es el método nativo recomendado (y el predeterminado); `function_calling` es menos fiable y `json_mode` está obsoleto.
- **Temperatura 0:** se configura para reducir la variación, pero el modelo usado tiene valores de muestreo fijos y la ignora (por eso aparece un `UserWarning`). No garantiza exactitud ni determinismo.
- **Coherencia:** el esquema Pydantic no comprueba la relación entre `es_pertinente` y `sentimiento`; `validar_coherencia()` en `analisis.py` lo hace en código. Si la respuesta es incoherente, se trata como un error y no se guarda.
- **Duplicados:** cada envío recibe un UUID al enviarse. Ese UUID es el `id` del registro y `guardar_opinion` no escribe un id que ya exista; por eso «Reintentar guardado» puede pulsarse varias veces sin duplicar.
- **Escritura segura:** archivo temporal en `datos/` + `os.replace`. Evita archivos a medio escribir, pero no resuelve el acceso concurrente de varios usuarios.

## Notas sobre el catálogo

Algunas clasificaciones de `tipo` son discutibles:

- **DeepSeek (h009)** y **Qwen (h012):** marcados como `modelo abierto` porque publican pesos de sus modelos, aunque también tienen una aplicación de chat (podrían ser `asistente`).
- **Kimi (h013):** marcado como `asistente` (la app de chat), aunque Moonshot AI también publica modelos con pesos abiertos.
- **Llama (h006):** `modelo abierto` en el sentido de «pesos descargables»; su licencia tiene restricciones y no es software libre en sentido estricto.
- **Stable Diffusion (h019):** marcado como `imágenes`, aunque también es un modelo abierto.
- **NotebookLM (h015)** y **Perplexity (h011):** marcados como `asistente`; no hay una categoría de «investigación» o «búsqueda» en la lista.
- **GitHub Copilot (h005):** GitHub pertenece a Microsoft; se mantiene «GitHub» como empresa.
