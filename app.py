import os
import re
import hashlib
import json
import base64
import zipfile
import io
from datetime import datetime
import streamlit as st
from collections import Counter
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from audio_recorder_streamlit import audio_recorder
from streamlit_agraph import agraph, Node, Edge, Config

try:
    import PyPDF2
except ImportError:
    pass

from groq import Groq

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Kelea Digital Brain", page_icon="🧠", layout="wide")

# --- INICIALIZACIÓN ---
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


@st.cache_resource
def get_groq_client():
    if GROQ_API_KEY: return Groq(api_key=GROQ_API_KEY)
    return None

cliente_groq = get_groq_client()

INBOX_FILE = "inbox.md"
CONOCIMIENTO_DIR = "Cerebro_Digital"
ARCHIVOS_DIR = os.path.join(CONOCIMIENTO_DIR, "Archivos_Originales")
HASHES_FILE = os.path.join(CONOCIMIENTO_DIR, "hashes_conocidos.json")
HISTORIAL_FILE = os.path.join(CONOCIMIENTO_DIR, "historial_busquedas.json")
LOGROS_FILE = os.path.join(CONOCIMIENTO_DIR, "logros.json")

# Inicializamos el estado de logros
if "logros" not in st.session_state:
    if os.path.exists(LOGROS_FILE):
        with open(LOGROS_FILE, 'r', encoding='utf-8') as f:
            st.session_state.logros = json.load(f)
    else:
        st.session_state.logros = {
            "puntos": 0,
            "notas_procesadas": 0,
            "racha_dias": 0,
            "ultima_fecha": ""
        }

for directorio in [CONOCIMIENTO_DIR, ARCHIVOS_DIR]:
    if not os.path.exists(directorio): os.makedirs(directorio)

# Cargamos el historial permanente al inicio
if "historial_busqueda" not in st.session_state:
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, 'r', encoding='utf-8') as f:
            st.session_state.historial_busqueda = json.load(f)
    else:
        st.session_state.historial_busqueda = []
if "query_ejecutada" not in st.session_state:
    st.session_state.query_ejecutada = ""

# --- ESTILOS CSS PERSONALIZADOS ---
st.markdown("""
<style>
    .badge {
        display: inline-block; padding: 0.25em 0.6em; font-size: 0.85em; font-weight: 700;
        line-height: 1; text-align: center; white-space: nowrap; border-radius: 0.5rem;
        background-color: #4CAF50; color: white; margin-right: 5px; margin-bottom: 5px;
    }
    .badge-tipo { background-color: #008CBA; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES CORE ---
def obtener_tamano_cerebro(directorio):
    """Calcula el tamaño total del directorio en bytes."""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(directorio):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # No contamos si el archivo se borró justo en ese momento
            if os.path.exists(fp):
                total_size += os.path.getsize(fp)
    return total_size

def mostrar_pdf(ruta_pdf):
    """Genera un iframe para visualizar el PDF dentro de Streamlit."""
    with open(ruta_pdf, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    # Creamos el HTML para el iframe
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def extraer_texto_archivo(ruta_archivo):
    ext = os.path.splitext(ruta_archivo)[1].lower()
    try:
        if ext in [".txt", ".md", ".py", ".js", ".html", ".css"]:
            with open(ruta_archivo, "r", encoding="utf-8") as f: return f.read(1500).replace("\n", " ").strip()
        elif ext == ".pdf":
            if 'PyPDF2' in globals():
                with open(ruta_archivo, "rb") as f:
                    lector = PyPDF2.PdfReader(f)
                    return lector.pages[0].extract_text()[:1500].replace("\n", " ").strip() if lector.pages else ""
        return f"[Archivo {ext} listo para procesar]"
    except Exception as e: return f"[Error: {e}]"

def analizar_con_groq(texto_inbox):
    """Enrutador Cognitivo: SIEMPRE devuelve 5 valores."""
    if not cliente_groq: 
        return "Error", ["#sin_api"], "Falta API Key", "Configurar .env", texto_inbox
    
    match_archivo = re.search(r"\*\*\[ARCHIVO: (.*?)\]\*\*", texto_inbox)
    es_archivo = bool(match_archivo)
    ruta_archivo = os.path.join(ARCHIVOS_DIR, match_archivo.group(1)) if es_archivo else ""
    ext = os.path.splitext(ruta_archivo)[1].lower() if es_archivo else ""

    prompt_base = """
    Eres el motor cognitivo de un 'Cerebro Digital'. Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta:
    {"tipo": "Categoría", "tags": ["#tag1"], "resumen": "Resumen corto", "accion": "Acción específica"}
    
    REGLA ESTRICTA PARA "tipo": 
    Debes clasificar el contenido analizando su naturaleza y asignarlo OBLIGATORIAMENTE a UNA de estas 10 carpetas exactas (no inventes ninguna otra):
    - Documentos
    - Imágenes
    - Videos
    - Audio
    - Descargas
    - Proyectos
    - Referencias
    - Temporales
    - Enlaces Web
    - Compartidos
    """
    
    # --- MODELOS ACTUALIZADOS ---
    MODELO_TEXTO = "llama-3.3-70b-versatile"
    MODELO_AUDIO = "whisper-large-v3"
    MODELO_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"
    
    transcripcion = ""
    imagen_b64 = None
    
    try:
        # 1. AUDIO (Uso de MODELO_AUDIO)
        if ext in [".mp3", ".wav", ".m4a"]:
            with open(ruta_archivo, "rb") as f:
                transcripcion = cliente_groq.audio.transcriptions.create(
                    file=(match_archivo.group(1), f.read()), 
                    model=MODELO_AUDIO # <--- Aplicada
                ).text
            prompt_user = f"{prompt_base}\nAnaliza este audio: {transcripcion}. En 'accion' extrae tareas."
            
        # 2. IMÁGENES (Uso de MODELO_VISION)
        elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
            with open(ruta_archivo, "rb") as f: imagen_b64 = base64.b64encode(f.read()).decode('utf-8')
            prompt_user = f"{prompt_base}\nHaz OCR y analiza esta imagen."
            
        # 3. VIDEOS (Uso de MODELO_TEXTO)
        elif ext in [".mp4", ".avi", ".mov"]:
            prompt_user = f"{prompt_base}\nAnaliza este video."
            
        # 4. TEXTO (Uso de MODELO_TEXTO)
        else:
            prompt_user = f"{prompt_base}\nAnaliza este contenido: {texto_inbox}"

        if imagen_b64:
            res = cliente_groq.chat.completions.create(
                messages=[{"role": "user", "content": [{"type": "text", "text": prompt_user}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagen_b64}"}}]}],
                model=MODELO_VISION, temperature=0.1)
        else:
            res = cliente_groq.chat.completions.create(messages=[{"role": "user", "content": prompt_user}], model=MODELO_TEXTO, temperature=0.1)
                
        json_str = re.search(r'\{.*\}', res.choices[0].message.content.strip(), re.DOTALL).group()
        datos = json.loads(json_str)
        texto_final = f"**[Transcripción]:** {transcripcion}\n\n{texto_inbox}" if transcripcion else texto_inbox
        return datos.get("tipo", "Nota"), datos.get("tags", []), datos.get("resumen", ""), datos.get("accion", ""), texto_final

    except Exception as e:
        return "Error", ["#revisar"], "Error IA", str(e), texto_inbox
    
def busqueda_semantica_groq(query, archivos_md):
    """
    Envía el catálogo de notas a Groq para que encuentre coincidencias semánticas.
    """
    if not cliente_groq:
        return []
    
    # 1. Construir un catálogo ligero con la metadata de las notas
    catalogo = []
    for f_name in archivos_md:
        ruta = os.path.join(CONOCIMIENTO_DIR, f_name)
        with open(ruta, "r", encoding="utf-8") as f:
            contenido = f.read()
            tipo, tags, cuerpo = parsear_markdown_estetico(contenido)
            
            # Extraemos el resumen para darle contexto a la IA sin enviarle todo el texto
            res_match = re.search(r">\s\*\*Resumen AI:\*\*\s(.*?)\n", cuerpo)
            resumen = res_match.group(1) if res_match else ""
            
            catalogo.append({
                "archivo": f_name,
                "tipo": tipo,
                "tags": tags,
                "resumen": resumen
            })
            
    # 2. Prompt para el enrutador de búsqueda
    prompt_busqueda = f"""
    Eres el motor de búsqueda semántica de un Cerebro Digital.
    El usuario ha introducido la siguiente búsqueda en lenguaje natural: "{query}"
    
    Aquí tienes el catálogo de las notas disponibles en formato JSON:
    {json.dumps(catalogo, ensure_ascii=False)}
    
    Tu tarea es analizar el significado de la búsqueda del usuario y compararlo con los resúmenes, tags y tipos de las notas.
    Devuelve ÚNICAMENTE un array JSON plano con los nombres de los archivos ("archivo") que mejor respondan a la búsqueda.
    Si ninguna nota tiene relación, devuelve [].
    Ejemplo de salida: ["nota_grafica.md", "apuntes_hardware_2.md"]
    """
    
    try:
        res = cliente_groq.chat.completions.create(
            messages=[{"role": "user", "content": prompt_busqueda}],
            model="llama-3.3-70b-versatile",
            temperature=0.1
        )
        # Extraer solo el array JSON de la respuesta
        json_str = re.search(r'\[.*\]', res.choices[0].message.content.strip(), re.DOTALL)
        if json_str:
            return json.loads(json_str.group())
        return []
    except Exception as e:
        st.error(f"Error en la IA de búsqueda: {e}")
        return []

def generar_preguntas_reflexion(archivos_encontrados):
    """
    Lee el contexto de los archivos encontrados y propone preguntas para conectar ideas.
    """
    if not cliente_groq or not archivos_encontrados: 
        return None
    
    # Recopilamos el contexto (resúmenes) de los primeros 5 archivos encontrados
    contexto = []
    for f_name in archivos_encontrados[:5]: 
        ruta = os.path.join(CONOCIMIENTO_DIR, f_name)
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                cuerpo = f.read()
                res_match = re.search(r">\s\*\*Resumen AI:\*\*\s(.*?)\n", cuerpo)
                if res_match:
                    contexto.append(f"- Nota '{f_name}': {res_match.group(1)}")
    
    if not contexto:
        return "No hay suficientes resúmenes en estas notas para generar preguntas profundas."

    prompt_reflexion = f"""
    Eres el asistente cognitivo del usuario. Basándote en el siguiente conjunto de notas que el usuario acaba de buscar:
    {chr(10).join(contexto)}
    
    Tu objetivo es fomentar el pensamiento crítico. Genera 3 preguntas de reflexión que ayuden al usuario a:
    1. Conectar las ideas de estas notas entre sí.
    2. Identificar posibles lagunas de conocimiento.
    3. Plantear cómo podría aplicar esta información de forma práctica.
    
    Devuelve ÚNICAMENTE las preguntas en formato de lista Markdown con viñetas, sin introducciones ni conclusiones.
    """
    
    try:
        res = cliente_groq.chat.completions.create(
            messages=[{"role": "user", "content": prompt_reflexion}],
            model="llama-3.3-70b-versatile",
            temperature=0.6 # Un poco más de creatividad para preguntas interesantes
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"Error al generar reflexión: {e}"

def guardar_conocimiento(texto, tipo, tags, titulo, resumen, accion):
    """Guarda nota y sincroniza el nombre del archivo original físico."""
    nombre_base = re.sub(r'[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ\s_]', '', titulo).replace(' ', '_')
    if not nombre_base: nombre_base = "nota"

    # Sincronización del Archivo Original
    match_archivo = re.search(r"\*\*\[ARCHIVO: (.*?)\]\*\*", texto)
    if match_archivo:
        nombre_viejo = match_archivo.group(1)
        ext_orig = os.path.splitext(nombre_viejo)[1]
        ruta_vieja = os.path.join(ARCHIVOS_DIR, nombre_viejo)
        nuevo_nom_fisico = f"{nombre_base}{ext_orig.lower()}"
        ruta_nueva = os.path.join(ARCHIVOS_DIR, nuevo_nom_fisico)

        if os.path.exists(ruta_vieja) and not os.path.exists(ruta_nueva):
            os.rename(ruta_vieja, ruta_nueva)
            texto = texto.replace(f"[ARCHIVO: {nombre_viejo}]", f"[ARCHIVO: {nuevo_nom_fisico}]")
            for h, v in registro_hashes.items():
                if v == f"Archivo: {nombre_viejo}": registro_hashes[h] = f"Archivo: {nuevo_nom_fisico}"
            with open(HASHES_FILE, 'w') as f: json.dump(registro_hashes, f)

    # Nota .md Autoincremental
    nombre_md = f"{nombre_base}.md"
    ruta_md = os.path.join(CONOCIMIENTO_DIR, nombre_md)
    cont = 1
    while os.path.exists(ruta_md):
        nombre_md = f"{nombre_base}_{cont}.md"
        ruta_md = os.path.join(CONOCIMIENTO_DIR, nombre_md)
        cont += 1
    
    contenido = f"---\ntipo: {tipo}\nfecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\ntags: {tags}\n---\n\n"
    if resumen: contenido += f"> **Resumen AI:** {resumen}\n>\n"
    if accion: contenido += f"> **Acción sugerida:** {accion}\n\n---\n\n{texto}"
    
    with open(ruta_md, "w", encoding="utf-8") as f: f.write(contenido)

def parsear_markdown_estetico(contenido):
    match = re.search(r"^---\n(.*?)\n---\n(.*)", contenido, re.DOTALL)
    if match:
        front = match.group(1)
        tipo = re.search(r"tipo:\s*(.*)", front).group(1) if "tipo:" in front else "Nota"
        tags = re.search(r"tags:\s*\[(.*?)\]", front).group(1).split(',') if "tags:" in front else []
        return tipo, [t.strip() for t in tags if t.strip()], match.group(2).strip()
    return "Nota", [], contenido

@st.cache_data(ttl=60)
def obtener_zip_cerebro():
    """Comprime el Cerebro Digital estructurándolo en carpetas reales por Temas dentro del ZIP."""
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        archivos_md = [f for f in os.listdir(CONOCIMIENTO_DIR) if f.endswith('.md')]
        
        # 1. Organizar las notas .md en carpetas según su Tema
        for f_name in archivos_md:
            ruta_md = os.path.join(CONOCIMIENTO_DIR, f_name)
            with open(ruta_md, 'r', encoding='utf-8') as f:
                contenido = f.read()
                # Extraemos el tema usando tu función existente
                tipo_tema, _, _ = parsear_markdown_estetico(contenido)
            
            # Limpiamos el nombre del tema por si acaso (evitar caracteres raros en carpetas)
            tema_seguro = tipo_tema if tipo_tema else "Sin_Clasificar"
            tema_seguro = "".join(c for c in tema_seguro if c.isalnum() or c in (' ', '_')).strip()
            
            # Escribimos el archivo en el ZIP indicando su nueva ruta de carpeta
            ruta_zip = f"{tema_seguro}/{f_name}"
            zf.write(ruta_md, arcname=ruta_zip)
            
        # 2. Añadir la carpeta de Archivos Originales (como repositorio de adjuntos central)
        if os.path.exists(ARCHIVOS_DIR):
            for f_name in os.listdir(ARCHIVOS_DIR):
                ruta_archivo = os.path.join(ARCHIVOS_DIR, f_name)
                if os.path.isfile(ruta_archivo):
                    zf.write(ruta_archivo, arcname=f"Archivos_Originales/{f_name}")
                    
    return mem_zip.getvalue()

# --- BARRA DE NAVEGACIÓN SUPERIOR ---
if "goto_menu" not in st.session_state:
    st.session_state.goto_menu = None

if st.session_state.goto_menu is not None:
    st.session_state.menu = st.session_state.goto_menu
    st.session_state.goto_menu = None

col_logo, col_nav = st.columns([0.4, 0.6])

with col_logo:
    # Mostramos el título de la app en la esquina superior izquierda
    st.markdown("### Kelea Digital Brain")

with col_nav:
    # Alineamos el menú a la derecha usando un contenedor
    st.write("") # Pequeño espaciador para alinear verticalmente con el título
    menu = st.radio(
        "Navegación", 
        ["Capturar", "Procesar", "Buscar"], 
        horizontal=True, 
        label_visibility="collapsed",
        key="menu"
    )

st.divider()

# --- INTERFAZ ---
st.sidebar.title("Kelea Digital Brain")
with st.sidebar.container(border=True):
    st.write("**Nivel de Cerebro**")
    c1, c2, c3 = st.columns(3)
    c1.metric(label="Puntos XP", value=st.session_state.logros["puntos"])
    c2.metric(label="Notas", value=st.session_state.logros["notas_procesadas"])
    c3.metric(label="Racha", value=f"{st.session_state.logros['racha_dias']} 🔥")
    
    # Barra de progreso para el siguiente "Nivel" (cada 500 puntos sube de nivel)
    nivel_actual = (st.session_state.logros["puntos"] // 500) + 1
    progreso = (st.session_state.logros["puntos"] % 500) / 500
    st.caption(f"Nivel {nivel_actual} - Faltan {500 - (st.session_state.logros['puntos'] % 500)} XP para subir")
    st.progress(progreso)

st.sidebar.divider()
# --- NUEVO: BOTÓN DE EXPORTACIÓN ---
st.sidebar.write("**Exportación Abierta**")
st.sidebar.caption("Descarga tu Cerebro Digital estructurado.")
        
# Llamamos a la función para generar el ZIP en memoria
datos_zip = obtener_zip_cerebro()
        
# Dibujamos el botón de descarga nativo de Streamlit
st.sidebar.download_button(
    label="Exportar Cerebro a .ZIP",
    data=datos_zip,
    file_name=f"Kelea_Digital_Brain_{datetime.now().strftime('%Y%m%d')}.zip",
    mime="application/zip",
    use_container_width=True,
    help="Descarga todas tus notas organizadas en carpetas y tus archivos multimedia originales."
)
        
        

try:
    # 1. Almacenamiento
    megas_u = obtener_tamano_cerebro(CONOCIMIENTO_DIR) / (1024 * 1024)
    st.sidebar.write(f"**Almacenamiento**")
    st.sidebar.progress(min(megas_u / 1024, 1.0))
    st.sidebar.caption(f"{megas_u:.2f} MB / 1024 MB usados")

    # 2. Análisis de Contenido y Explorador de Carpetas
    archivos_md = [f for f in os.listdir(CONOCIMIENTO_DIR) if f.endswith('.md')]
    tags_l = []
    temas_dict = {} # Diccionario para las carpetas
    
    for f_name in archivos_md:
        with open(os.path.join(CONOCIMIENTO_DIR, f_name), 'r', encoding='utf-8') as f:
            tipo_tema, tg, _ = parsear_markdown_estetico(f.read())
            tags_l.extend(tg)
            
            # Agrupamos los archivos en su tema correspondiente
            tema_seguro = tipo_tema if tipo_tema else "Sin Clasificar"
            if tema_seguro not in temas_dict:
                temas_dict[tema_seguro] = []
            temas_dict[tema_seguro].append(f_name)

    if archivos_md:
        st.sidebar.divider()
        
        # --- CARPETAS VIRTUALES (TEMAS) ---
        st.sidebar.write("**Explorador por Temas**")
        
        for tema, archivos in sorted(temas_dict.items()):
            # st.sidebar.expander actúa como una carpeta desplegable
            with st.sidebar.expander(f"{tema} ({len(archivos)})"):
                for f_name in sorted(archivos):
                    nombre_limpio = f_name.replace(".md", "").replace("_", " ")
                    
                    # Botón por cada archivo. Al hacer clic, te lleva a la vista detallada
                    if st.button(f"{nombre_limpio}", key=f"nav_folder_{f_name}", use_container_width=True):
                        # Le decimos a la app que busque exactamente este archivo
                        st.session_state.search_query = nombre_limpio
                        st.session_state.query_ejecutada = nombre_limpio
                        st.session_state.goto_menu = "Buscar"
                        st.rerun()
        
        st.sidebar.divider()
        
        # 3. TOP 3 TAGS (Mantenemos tu código original aquí)
        if tags_l:
            st.sidebar.write("**Top 3 Etiquetas**")
            top_3 = Counter(tags_l).most_common(3)
            for tag, count in top_3:
                tag = str(tag).strip().strip("'\"").lstrip("#")
                st.sidebar.markdown(f'<span class="badge">#{tag} ({count})</span>', unsafe_allow_html=True)
        
        # 4. HISTORIAL DE BÚSQUEDA PERMANENTE (Botones clicables)
        if st.session_state.historial_busqueda:
            st.sidebar.write("**Últimas búsquedas**")
            for h in st.session_state.historial_busqueda:
                # Al hacer clic, actualizamos la variable y recargamos
                if st.sidebar.button(f"{h}", key=f"hist_{h}", use_container_width=True):
                    st.session_state.search_query = h
                    st.session_state.query_ejecutada = h
                    st.session_state.goto_menu = "Buscar"
                    st.rerun()
            
            if st.sidebar.button("Limpiar historial", type="secondary"):
                st.session_state.historial_busqueda = []
                if os.path.exists(HISTORIAL_FILE): os.remove(HISTORIAL_FILE)
                st.session_state.query_ejecutada = ""
                st.session_state.search_query = ""
                st.session_state.goto_menu = "Buscar"
                st.rerun()
except Exception as e:
    st.sidebar.error(e)

st.sidebar.divider()

registro_hashes = {}
if os.path.exists(HASHES_FILE):
    try:
        with open(HASHES_FILE, 'r') as f: registro_hashes = json.load(f)
    except: pass

if menu == "Capturar":
    st.subheader("Inbox Rápido")
    
    # --- GESTIÓN DE NOTIFICACIONES ---
    if "notificacion" in st.session_state:
        c_msg, c_x = st.columns([0.9, 0.1])
        with c_msg: getattr(st, st.session_state.notificacion[0])(st.session_state.notificacion[1])
        with c_x: 
            if st.button("❌", key="close_noti"): 
                del st.session_state.notificacion
                st.rerun()

    # --- ESTADO DEL INBOX (NUEVO: Botón de vaciado) ---
    if os.path.exists(INBOX_FILE):
        with open(INBOX_FILE, "r", encoding="utf-8") as f:
            lineas = [l for l in f.readlines() if l.strip()]
        
        if lineas:
            col_info, col_nuke = st.columns([0.7, 0.3])
            col_info.info(f"Tienes **{len(lineas)}** elementos pendientes de procesar.")
            
            # NUEVO: Aviso de acumulación
            if len(lineas) >= 5:
                st.warning("Tu Inbox se está llenando. Recuerda procesar la información pronto para evitar la fricción cognitiva.")
            if col_nuke.button("Vaciar Inbox", use_container_width=True, help="Borra todos los elementos pendientes"):
                os.remove(INBOX_FILE)
                st.session_state.notificacion = ("success", "Inbox vaciado por completo.")
                st.rerun()
    
    st.divider()

    # 1. NOTAS DE TEXTO
    with st.form("form_texto", clear_on_submit=True):
        txt = st.text_area("Captura una idea rápida:")
        if st.form_submit_button("Guardar Texto") and txt:
            h = hashlib.sha256(txt.encode()).hexdigest()
            if h in registro_hashes: 
                st.session_state.notificacion = ("warning", "Ya lo tienes.")
            else:
                registro_hashes[h] = f"Texto: {txt[:20]}..."
                with open(INBOX_FILE, "a", encoding="utf-8") as f: f.write(f"- {txt}\n")
                with open(HASHES_FILE, "w") as f: json.dump(registro_hashes, f)
                st.session_state.notificacion = ("success", "¡Idea guardada!")
            st.rerun()

    # 2. ARCHIVOS MULTIMEDIA
    with st.form("form_archivo", clear_on_submit=True):
        up = st.file_uploader("Sube archivos:", type=["pdf", "png", "jpg", "jpeg", "mp3", "wav", "m4a", "py", "js", "mp4", "avi", "mov"])
        if st.form_submit_button("Guardar Archivo") and up:
            
            data = up.getvalue()
            h = hashlib.sha256(data).hexdigest()
            path = os.path.join(ARCHIVOS_DIR, up.name)
            fantasma = h in registro_hashes and not os.path.exists(os.path.join(ARCHIVOS_DIR, registro_hashes[h].replace("Archivo: ", "")))

            if h in registro_hashes and not fantasma: st.session_state.notificacion = ("error", "Duplicado.")
            elif os.path.exists(path) and not fantasma: st.session_state.notificacion = ("error", "Nombre en uso.")
            else:
                with open(path, "wb") as f: f.write(data)
                registro_hashes[h] = f"Archivo: {up.name}"
                with open(INBOX_FILE, "a", encoding="utf-8") as f: f.write(f"- **[ARCHIVO: {up.name}]** {extraer_texto_archivo(path)}\n")
                with open(HASHES_FILE, "w") as f: json.dump(registro_hashes, f)
                st.session_state.notificacion = ("success", "Guardado.")
            st.rerun()

    st.divider()
    
    # 3. GRABACIÓN DE VOZ EN DIRECTO
    st.subheader("Grabadora de Voz")
    audio_bytes = audio_recorder(text="Haz clic para grabar", icon_size="2x", key="grabadora_directo")

    if audio_bytes:
        # Generamos el hash para evitar duplicados accidentales
        h_voz = hashlib.sha256(audio_bytes).hexdigest()
        
        # Usamos una variable de sesión para procesar cada audio SOLO UNA VEZ
        if "ultimo_audio_hash" not in st.session_state or st.session_state.ultimo_audio_hash != h_voz:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_voz = f"Nota_Voz_{timestamp}.wav"
            ruta_voz = os.path.join(ARCHIVOS_DIR, nombre_voz)
            
            # 1. Guardar el archivo físico
            try:
                with open(ruta_voz, "wb") as f:
                    f.write(audio_bytes)
                
                # 2. Registrar el hash
                registro_hashes[h_voz] = f"Archivo: {nombre_voz}"
                with open(HASHES_FILE, "w") as f:
                    json.dump(registro_hashes, f)
                
                # 3. Escribir en el Inbox (¡Aquí es donde fallaba!)
                # Forzamos el guardado con flush para que no se pierda al reiniciar
                with open(INBOX_FILE, "a", encoding="utf-8") as f:
                    f.write(f"- **[ARCHIVO: {nombre_voz}]** [Grabación de voz lista]\n")
                    f.flush() 
                
                # Guardamos en sesión que ya hemos procesado ESTE audio
                st.session_state.ultimo_audio_hash = h_voz
                
                st.success(f"¡Nota capturada y enviada al Inbox: {nombre_voz}!")
                
                # Pequeña pausa para que el usuario vea el éxito antes del rerun
                import time
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"Error crítico al guardar el audio: {e}")

elif menu == "Procesar":
    st.subheader("Validar y Estructurar Conocimiento")
    
    if not os.path.exists(INBOX_FILE):
        st.info("¡Inbox limpio! No hay nada pendiente de procesar.")
    else:
        with open(INBOX_FILE, "r", encoding="utf-8") as f:
            # Filtramos líneas vacías y limpiamos el formato de lista Markdown
            entradas_raw = [linea.strip() for linea in f.readlines() if linea.strip()]
        
        if not entradas_raw:
            st.info("¡Inbox limpio! No hay nada pendiente.")
        else:
            # 1. SELECTOR DE ENTRADA (Para no ir en orden)
            st.subheader("Elige qué procesar")
            
            # Creamos etiquetas amigables para el selector
            opciones = []
            for e in entradas_raw:
                texto_limpio = e.lstrip("- ").strip()
                # Si es un archivo, mostramos el nombre; si es texto, los primeros 40 caracteres
                if "[ARCHIVO:" in texto_limpio:
                    label = "" + re.search(r"\[ARCHIVO: (.*?)\]", texto_limpio).group(1)
                else:
                    label = "" + (texto_limpio[:50] + "..." if len(texto_limpio) > 50 else texto_limpio)
                opciones.append(label)

            seleccion_idx = st.selectbox(
                "Tienes elementos pendientes en el Inbox:",
                range(len(opciones)),
                format_func=lambda x: opciones[x]
            )
            
            entrada_seleccionada = entradas_raw[seleccion_idx].lstrip("- ").strip()

            # Reiniciamos la sugerencia de la IA si cambiamos de selección
            if "sug" not in st.session_state or st.session_state.get("last_idx") != seleccion_idx:
                with st.spinner("El Router Cognitivo está analizando tu selección..."):
                    st.session_state.sug = analizar_con_groq(entrada_seleccionada)
                    st.session_state.last_idx = seleccion_idx
            
            tipo_p, tags_p, res_p, acc_p, txt_f = st.session_state.sug
            
            st.divider()
            
            # 2. PANEL DE TRABAJO (Visor + Control)
            col_visor, col_control = st.columns([1.2, 1])
            
            with col_visor:
                st.subheader("Visor de Entrada")
                m = re.search(r"\*\*\[ARCHIVO: (.*?)\]\*\*", entrada_seleccionada)
                if m:
                    nombre_archivo = m.group(1)
                    p = os.path.join(ARCHIVOS_DIR, nombre_archivo)
                    if os.path.exists(p):
                        ext = os.path.splitext(nombre_archivo)[1].lower()
                        
                        # --- LÓGICA MULTIMEDIA ACTUALIZADA ---
                        if ext in [".png", ".jpg", ".jpeg", ".webp"]:
                            st.image(p, use_container_width=True)
                        elif ext in [".mp3", ".wav", ".m4a"]:
                            st.audio(p)
                        elif ext in [".mp4", ".webm", ".avi"]:
                            st.video(p)
                        elif ext == ".pdf": # <--- NUEVA PREVISUALIZACIÓN DE PDF
                            mostrar_pdf(p)
                
                st.text_area("Contenido extraído:", value=txt_f, height=150, disabled=True)
                
            with col_control:
                st.subheader("Panel de Control")
                # El sistema propone, tú validas
                tit_f = st.text_input("Título de la Nota:", value=nombre_archivo.split('.')[0] if m else "Nueva Nota")
                res_f = st.text_area("Resumen AI:", value=res_p, height=120)
                acc_f = st.text_area("Acción sugerida:", value=acc_p, height=100)
                
                c1, c2 = st.columns(2)
                tipo_f = c1.text_input("Categoría:", value=tipo_p)
                tags_f = c2.text_input("Etiquetas (espacio):", value=" ".join(tags_p))
                
                # BOTONES DE ACCIÓN
                st.write("")
                if st.button("Guardar y Archivar", type="primary", use_container_width=True):
                    # Guardamos la nota
                    guardar_conocimiento(txt_f, tipo_f, tags_f.split(), tit_f, res_f, acc_f)
                    
                    # --- NUEVO: ACTUALIZAR LOGROS ---
                    fecha_hoy = datetime.now().strftime('%Y-%m-%d')
                    st.session_state.logros["puntos"] += 50  # +50 XP por nota procesada
                    st.session_state.logros["notas_procesadas"] += 1
                    
                    # Eliminamos SOLO la entrada seleccionada del Inbox (tu código existente)
                    if st.session_state.logros["ultima_fecha"] != fecha_hoy:
                        # Si es un día nuevo, sumamos 1 a la racha
                        st.session_state.logros["racha_dias"] += 1
                        st.session_state.logros["ultima_fecha"] = fecha_hoy
                        st.toast("🔥 ¡Racha diaria aumentada!", icon="🔥")
                    
                    st.toast(f"¡+50 XP! Total: {st.session_state.logros['puntos']} XP", icon="🎮")
                    
                    with open(LOGROS_FILE, "w", encoding="utf-8") as f:
                        json.dump(st.session_state.logros, f)
                    
                    nuevas_entradas = [entradas_raw[i] + "\n" for i in range(len(entradas_raw)) if i != seleccion_idx]
                    with open(INBOX_FILE, "w", encoding="utf-8") as f:
                        f.writelines(nuevas_entradas)
                    
                    # Limpiamos sesión y recargamos
                    del st.session_state.sug
                    st.rerun()

                if st.button("Descartar este elemento", use_container_width=True):
                    # Eliminamos el archivo físico si es un archivo para no dejar basura
                    if m:
                        ruta_p = os.path.join(ARCHIVOS_DIR, m.group(1))
                        if os.path.exists(ruta_p): os.remove(ruta_p)
                    
                    # Eliminamos SOLO la entrada seleccionada del Inbox
                    nuevas_entradas = [entradas_raw[i] + "\n" for i in range(len(entradas_raw)) if i != seleccion_idx]
                    with open(INBOX_FILE, "w", encoding="utf-8") as f:
                        f.writelines(nuevas_entradas)
                    
                    del st.session_state.sug
                    st.rerun()

elif menu == "Buscar":
    st.subheader("Explorar y Gestionar Conocimiento")
    
    # Creamos dos pestañas para separar la búsqueda del mapa visual
    tab_buscar, tab_mapa = st.tabs(["Búsqueda Clásica", "Mapa Conceptual (Cerebro)"])
    
    if "edit_target" not in st.session_state:
        st.session_state.edit_target = None

    # ==========================================
    # PESTAÑA 2: MAPA CONCEPTUAL (CEREBRO DIGITAL)
    # ==========================================
    with tab_mapa:
        st.subheader("Tu Cerebro Digital Interconectado")
        st.caption("🔴 Temas | 🔵 Notas | 🟢 Etiquetas (Tags). Haz **UN SOLO CLIC** en los nodos para inspeccionarlos (evita el doble clic).")
        
        archivos_md = [f for f in os.listdir(CONOCIMIENTO_DIR) if f.endswith(".md")]
        
        if not archivos_md:
            st.info("Aún no tienes notas procesadas para mostrar en el mapa.")
        else:
            nodes = []
            edges = []
            temas_registrados = set()
            tags_registrados = set() 
            
            for f_name in archivos_md:
                ruta = os.path.join(CONOCIMIENTO_DIR, f_name)
                with open(ruta, "r", encoding="utf-8") as f:
                    contenido = f.read()
                    tipo_tema, tags, _ = parsear_markdown_estetico(contenido)
                
                tema_seguro = tipo_tema if tipo_tema else "Sin Clasificar"
                id_nota = f_name.replace(".md", "")
                
                # Crear el nodo del TEMA (Hexágono Rojo)
                if tema_seguro not in temas_registrados:
                    nodes.append(Node(id=tema_seguro, label=tema_seguro.upper(), size=30, color="#FF4B4B", shape="hexagon"))
                    temas_registrados.add(tema_seguro)
                
                # Crear el nodo de la NOTA (Círculo Azul)
                nodes.append(Node(id=id_nota, label=id_nota.replace("_", " "), size=20, color="#008CBA", shape="dot"))
                
                # Conectar la NOTA con su TEMA (Línea sólida roja)
                edges.append(Edge(source=id_nota, target=tema_seguro, color="#FF4B4B"))
                
                # NUEVO: Crear nodos de TAGS y conectarlos a la nota
                for tag in tags:
                    tag_clean = f"#{str(tag).strip().strip(chr(39)+chr(34)).lstrip('#')}"
                    
                    if tag_clean not in tags_registrados:
                        nodes.append(Node(id=tag_clean, label=tag_clean, size=15, color="#4CAF50", shape="diamond"))
                        tags_registrados.add(tag_clean)
                    
                    # Conectar Nota -> Tag (Línea gris punteada para diferenciarla)
                    edges.append(Edge(source=id_nota, target=tag_clean, color="#A0A0A0", dashed=True))

            config = Config(
                width="100%",
                height=600,
                directed=False, 
                physics=True, 
                hierarchical=False,
                nodeHighlightBehavior=True,
                highlightColor="#F7A7A6",
                collapsible=False
            )

            # Llamada corregida SIN el parámetro 'key'
            nodo_raw = agraph(nodes=nodes, edges=edges, config=config)
            
            # REACCIÓN INMEDIATA AL CLIC
            if nodo_raw:
                # Control de seguridad: algunas versiones devuelven una lista si dejas el ratón pulsado
                if isinstance(nodo_raw, list):
                    nodo_seleccionado = nodo_raw[0] if len(nodo_raw) > 0 else None
                else:
                    nodo_seleccionado = nodo_raw
                
                if nodo_seleccionado:
                    st.divider()
                    
                    # Si el usuario ha hecho clic en una NOTA (sabemos que es nota si existe su .md)
                    if f"{nodo_seleccionado}.md" in archivos_md:
                        with open(os.path.join(CONOCIMIENTO_DIR, f"{nodo_seleccionado}.md"), "r", encoding="utf-8") as f:
                            contenido = f.read()
                        
                        # Usamos tu función para separar los metadatos del texto real
                        t, tg, c = parsear_markdown_estetico(contenido)
                        
                        # Creamos una tarjeta visualmente atractiva
                        with st.container(border=True):
                            st.subheader(f"{nodo_seleccionado.replace('_', ' ')}")
                            
                            tags_html = ""
                            for tag in tg:
                                clean_tag = str(tag).strip().strip(chr(39)+chr(34)).lstrip("#")
                                tags_html += f'<span class="badge">#{clean_tag}</span>'
                            
                            st.markdown(
                                f'<span class="badge badge-tipo">{t}</span>' + tags_html,
                                unsafe_allow_html=True
                            )
                            
                            st.divider()
                            st.markdown(c)
                            
                            # RENDERIZAR ARCHIVOS MULTIMEDIA Y BOTÓN
                            m = re.search(r"\*\*\[ARCHIVO: (.*?)\]\*\*", c)
                            if m:
                                p = os.path.join(ARCHIVOS_DIR, m.group(1))
                                if os.path.exists(p):
                                    st.divider()
                                    ext = p.lower()
                                    if ext.endswith((".png", ".jpg", ".jpeg", ".webp")):
                                        st.image(p, use_container_width=True)
                                    elif ext.endswith((".mp3", ".wav", ".m4a")):
                                        st.audio(p)
                                    elif ext.endswith((".mp4", ".webm", ".avi", ".mov")):
                                        st.video(p)
                                    elif ext.endswith(".pdf"):
                                        mostrar_pdf(p)
                                    
                                    st.write("") 
                                    st.download_button(
                                        label="Descargar archivo original",
                                        data=open(p, "rb"),
                                        file_name=m.group(1),
                                        key=f"dl_mapa_{nodo_seleccionado}"
                                    )
                    # Si el usuario ha hecho clic en un TEMA o TAG
                    else:
                        st.info(f"Has seleccionado la categoría o etiqueta: **{nodo_seleccionado}**")

    # --- MODO EDICIÓN ---
    if st.session_state.edit_target:
        f_name = st.session_state.edit_target
        ruta_md = os.path.join(CONOCIMIENTO_DIR, f_name)
        
        if not os.path.exists(ruta_md):
            st.session_state.edit_target = None
            st.rerun()

        with open(ruta_md, 'r', encoding='utf-8') as f:
            contenido_completo = f.read()
            tipo_e, tags_e, cuerpo_e = parsear_markdown_estetico(contenido_completo)
        
        # Extracción selectiva de campos (Regex ajustado)
        res_match = re.search(r">\s\*\*Resumen AI:\*\*\s(.*?)\n", cuerpo_e)
        acc_match = re.search(r">\s\*\*Acción sugerida:\*\*\s(.*?)\n", cuerpo_e)
        texto_limpio = cuerpo_e.split("---")[-1].strip()
        
        st.subheader(f"Editando: {f_name}")
        col_back, col_nuke = st.columns([0.8, 0.2])
        if col_back.button("Cancelar"):
            st.session_state.edit_target = None
            st.rerun()

        # BOTÓN DE BORRADO DEFINITIVO
        if col_nuke.button("ELIMINAR TODO", type="secondary", help="Borra la nota y el archivo físico"):
            match_archivo = re.search(r"\*\*\[ARCHIVO: (.*?)\]\*\*", cuerpo_e)
            if match_archivo:
                nombre_f = match_archivo.group(1)
                ruta_f = os.path.join(ARCHIVOS_DIR, nombre_f)
                if os.path.exists(ruta_f): os.remove(ruta_f)
                for h, v in list(registro_hashes.items()):
                    if v == f"Archivo: {nombre_f}": del registro_hashes[h]
                with open(HASHES_FILE, 'w') as f: json.dump(registro_hashes, f)
            
            os.remove(ruta_md)
            st.session_state.edit_target = None
            st.success("Nota y archivos eliminados físicamente.")
            st.rerun()

        with st.container(border=True):
            c1, c2 = st.columns(2)
            with c1:
                nuevo_tit = st.text_input("Título:", value=f_name.replace(".md", ""))
                nuevo_res = st.text_area("Resumen:", value=res_match.group(1) if res_match else "", height=150)
            with c2:
                nueva_cat = st.text_input("Categoría:", value=tipo_e)
                nuevos_tags = st.text_input("Etiquetas:", value=" ".join(tags_e))
                nueva_acc = st.text_area("Acción:", value=acc_match.group(1) if acc_match else "", height=150)
            
            if st.button("Guardar Cambios", type="primary", use_container_width=True):
                if f"{nuevo_tit}.md" != f_name: os.remove(ruta_md)
                guardar_conocimiento(texto_limpio, nueva_cat, nuevos_tags.split(), nuevo_tit, nuevo_res, nueva_acc)
                st.session_state.edit_target = None
                st.rerun()

    # --- MODO BÚSQUEDA ---
    else:
        if "query_ejecutada" not in st.session_state: st.session_state.query_ejecutada = ""
        if "historial_busqueda" not in st.session_state: st.session_state.historial_busqueda = []

        # Form de búsqueda
        with st.form("buscador", clear_on_submit=False):
            st.text_input("Busca por contenido, título o #tag:", key="search_query")
            # NUEVO: Toggle para activar la búsqueda con IA
            modo_ia = st.toggle("Búsqueda Inteligente (Semántica)", help="La IA leerá tu frase y buscará archivos relacionados por contexto, no solo por coincidencia de palabras.")
            submitted = st.form_submit_button("Buscar")

        if submitted:
            q_now = st.session_state.search_query.strip()
            if q_now:
                if q_now in st.session_state.historial_busqueda: st.session_state.historial_busqueda.remove(q_now)
                st.session_state.historial_busqueda.insert(0, q_now)
                st.session_state.historial_busqueda = st.session_state.historial_busqueda[:10]
                st.session_state.query_ejecutada = q_now
                with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
                    json.dump(st.session_state.historial_busqueda, f, ensure_ascii=False)
                st.rerun()

        # 2) Render de resultados
        q = st.session_state.query_ejecutada.strip()
        if q:
            archivos = [f for f in os.listdir(CONOCIMIENTO_DIR) if f.endswith(".md")]
            archivos_encontrados = []

            # --- LÓGICA DE FILTRADO ---
            if modo_ia:
                with st.spinner("La IA está analizando tu Cerebro Digital..."):
                    archivos_encontrados = busqueda_semantica_groq(q, archivos)
            else:
                # Búsqueda léxica mejorada
                q_norm = q.lower().strip()
                for f_name in archivos:
                    # Normalizamos el nombre del archivo para que "olas mar" coincida con "olas_mar.md"
                    f_name_norm = f_name.lower().replace("_", " ").replace(".md", "")
                    
                    with open(os.path.join(CONOCIMIENTO_DIR, f_name), "r", encoding="utf-8") as f:
                        contenido = f.read().lower()
                        
                        # Buscamos en el contenido O en el nombre del archivo normalizado
                        if q_norm in contenido or q_norm in f_name_norm or q_norm in f_name.lower():
                            archivos_encontrados.append(f_name)

            # --- RENDERIZAR RESULTADOS ---
            if archivos_encontrados:
                st.success(f"Se han encontrado {len(archivos_encontrados)} notas relevantes.")
                
                for f_name in archivos_encontrados:
                    if not os.path.exists(os.path.join(CONOCIMIENTO_DIR, f_name)): continue
                    
                    with open(os.path.join(CONOCIMIENTO_DIR, f_name), "r", encoding="utf-8") as f:
                        cont = f.read()
                        
                    t, tg, c = parsear_markdown_estetico(cont)

                    with st.expander(f"{f_name.replace('_', ' ').replace('.md', '')}"):
                        tags_html = "".join([f'<span class="badge">#{str(tag).strip().strip(chr(39)+chr(34)).lstrip("#")}</span>' for tag in tg])
                        st.markdown(f'<span class="badge badge-tipo">{t}</span>' + tags_html, unsafe_allow_html=True)
                        st.markdown(c)

                        c_edit, _ = st.columns([0.2, 0.8])
                        if c_edit.button("Editar", key=f"e_{f_name}"):
                            st.session_state.edit_target = f_name
                            st.rerun()

                        # Visualización de archivos adjuntos
                        m = re.search(r"\[ARCHIVO:\s*(.*?)\]", c)
                        if m:
                            p = os.path.join(ARCHIVOS_DIR, m.group(1))
                            if os.path.exists(p):
                                st.divider()
                                ext = p.lower()
                                if ext.endswith((".png", ".jpg", ".jpeg", ".webp")): st.image(p)
                                elif ext.endswith((".mp3", ".wav", ".m4a")): st.audio(p)
                                elif ext.endswith((".mp4", ".avi", ".mov")): st.video(p)
                                elif ext.endswith(".pdf"): mostrar_pdf(p)
                                st.download_button("Descargar original", data=open(p, "rb"), file_name=m.group(1), key=f"dl_{f_name}")

                # --- SECCIÓN DE REFLEXIÓN (Solo si hay resultados) ---
                st.divider()
                st.subheader("💡 Reflexiona sobre tus notas")
                if st.button("Generar Preguntas de Reflexión", key=f"btn_ref_{q}", type="secondary"):
                    with st.spinner("Analizando contexto..."):
                        preguntas = generar_preguntas_reflexion(archivos_encontrados)
                        if preguntas: st.info(preguntas)
            
            else:
                # AHORA SÍ: Este mensaje se mostrará si archivos_encontrados está vacío
                st.info(f"No se han encontrado notas que coincidan con '**{q}**'.")
        
        else:
            st.info("Escribe una búsqueda y pulsa **Buscar**.")