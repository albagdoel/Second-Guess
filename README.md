#  Kelea Digital Brain: Elevando el Pensamiento Humano

> **"Transforma datos dispersos en conocimiento útil, organizado y reutilizable sin perder el foco."**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://streamlit.io/)
[![Groq Powered](https://img.shields.io/badge/AI-Groq%20Llama%203.3-orange)](https://groq.com/)

##  La Propuesta de Valor
- En un mundo saturado de información, el problema no es capturar datos, sino la **fricción cognitiva** que supone organizarlos mientras estamos concentrados en otra tarea.
- **Kelea Digital Brain** es una solución diseñada para eliminar esa fricción, permitiendo una captura instantánea y un procesado asistido por Inteligencia Artificial que respeta siempre el criterio humano.

---

##  Características Principales (Core & Extras)

### 1. Inbox Unificado "Zero-Friction"
- Punto único de entrada para capturar cualquier tipo de información sin necesidad de clasificar en el momento:
* **Notas rápidas de texto** e ideas sueltas.
* **Archivos multimedia** (PDF, Imágenes, Vídeo).
* **Grabadora de Voz integrada** con transcripción automática vía **Whisper-large-v3**.

### 2. Procesado Asistido (Human-in-the-Loop)
El sistema utiliza un **Router Cognitivo** basado en LLMs de alto rendimiento (Groq) para analizar el contenido:
* **Clasificación Inteligente:** Propone el destino entre 10 categorías clave como Proyectos, Referencias o Documentos.
* **Resúmenes y Acciones:** Genera resúmenes ejecutivos y detecta tareas específicas automáticamente.
* **Validación Humana:** El sistema propone, pero la persona siempre valida, corrige o descarta la información antes de archivarla.

### 3. Mapa Conceptual y Conexiones
Visualización de la información como un **cerebro interconectado** no lineal:
* **Grafo dinámico:** Nodos de Temas, Notas y Etiquetas (#tags) que permiten descubrir patrones y relaciones conceptuales.
* **Consulta Semántica:** Búsqueda inteligente por significado y contexto, superando la limitación de las palabras clave.
* **Preguntas de Reflexión:** La IA genera preguntas automáticas para fomentar el pensamiento crítico y conectar ideas existentes.

### 4. Gamificación y Motivación
Para evitar que el Inbox se vuelva abrumador, hemos gamificado el hábito de procesar:
* **Sistema de XP y Niveles:** Puntos por cada nota transformada en conocimiento.
* **Rachas Diarias (Streaks):** Fomento de la constancia para mantener un cerebro digital vivo.
* **Logros Visuales:** Dashboard de progreso integrado en la barra lateral.

### 5. Almacenamiento Abierto (Open & Portable)
Tus datos te pertenecen y son accesibles sin dependencias fuertes:
* **Formato Markdown:** Notas legibles por humanos y compatibles con herramientas como Obsidian o Logseq.
* **Exportación Estructurada:** Generación de un `.zip` organizado automáticamente por carpetas temáticas para una portabilidad total.

---

## Stack Tecnológico
* **Frontend:** Streamlit (Interfaz reactiva y ágil).
* **Cerebro IA:** Groq (Llama 3.3 Versatile, Llama 3.2 Vision & Whisper-large-v3).
* **Gráficos:** Streamlit-Agraph (Visualización de redes).
* **Almacenamiento:** Sistema de archivos local (Markdown + Repositorio binario).

---

## Instalación y Uso
1.  Clona el repositorio.
2.  Crea un archivo `.env` con tu `GROQ_API_KEY`.
3.  Instala las dependencias: `pip install -r requirements.txt`.
4.  Lanza la aplicación: `streamlit run app.py`.

---

## Roadmap / Futuras Mejoras
* [ ] **Extracción directa::** Se podrá extraer la información directamente utilizado atajos en teclado.
* [ ] **IA Local:** Integración con Ollama para privacidad total del conocimiento.
* [ ] **OCR Avanzado:** Extracción de tablas complejas en PDFs técnicos.
* [ ] **Ranking Social:** Sistema de competición de XP entre usuarios.

---

*Desarrollado para el **Hack UDC KELEA 2026** - Convirtiendo información dispersa en conocimiento útil.*

