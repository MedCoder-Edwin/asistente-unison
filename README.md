# Sistema RAG para Consulta Documental Institucional

Asistente conversacional basado en arquitectura **RAG (Retrieval-Augmented Generation)** diseñado para responder consultas de forma precisa, trazable y libre de alucinaciones a partir de documentación normativa y administrativa (reglamentos, convocatorias y manuales).

---

## Arquitectura del Pipeline

El flujo de datos consta de seis etapas secuenciales desde la ingesta documental hasta la generación de respuestas citadas:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. Base documental                                                      │
│    PDF · Reglamentos · Convocatorias · Manuales                         │
└────────────────────────────────────┬────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. Procesamiento y fragmentación                                        │
│    Extracción · Limpieza · Chunking · Metadata                          │
└────────────────────────────────────┬────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. Representación vectorial                                             │
│    BGE-M3 · Embeddings de 1024 dimensiones                              │
└────────────────────────────────────┬────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. Recuperación de información                                          │
│    ChromaDB · Búsqueda semántica · Top-K                                │
└────────────────────────────────────┬────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. Generación de respuestas                                             │
│    Qwen 2.5 3B · Prompt de control · Contexto recuperado                │
└────────────────────────────────────┬────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. Respuesta fundamentada                                               │
│    Respuesta · Referencias · Documento · Página                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Descripción técnica por etapas
1. **Ingesta de la base documental**:
Se cargan las fuentes (archivos en formato PDF) correspondientes a reglamentos, convocatorias y manuales. El objetivo es centralizar el corpus de conocimiento oficial que servirá como única fuente de verdad para el modelo

2. **Procesamiento y fragmentación**:
Extracción y limpieza de todo el texto plano, eliminando encabezados, caracteres corruptos y ruido tipográfico. En esta etapa se realiza un proceso de chunking (fragmentación / segmentación) de los documentos con un ligero solapamiento para preservar la continuidad semántica de los bloques.
Adicionalmente cada fragmento es etiquetado con su documento de origen y no. de página para garantizar la trazabilidad posterior. 

3. **Representación vectorial (Embeddings)**:
Uso del modelo bge-m3, seleccionado por su alto rendimiento multilingüe y soporte para contextos largos. Aqui cada chunk se proyecta en un vector de 1024 dimensiones que captura su significado semantico.

4. **Recuperación de información**:
Se utiliza ChromaDB para el almacenamiento e indexacion rapida. Ante una consulta del usuario, se calculo su embedding con bge-m3 y se recuperan los fragmentos mas relevantes mediante Top-K.

5. **Generacion de respuestas**:
Qwen2.5:3b ejecutado de forma local inyecta los fragmentos recuperados dentro de un prompt definido que instruye al modelo a responder unicamente con base en el contexto proporcionado, evitando alucinaciones

6. **Respuesta del modelo**:
Generacion de la respuesta en lenguaje natural acompañada de sus referencias explicitas (nombre del documento y no. de pagina exacto de donde se extrajo la informacion)
