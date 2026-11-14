# Sistema RAG para Consulta Documental Institucional

Asistente conversacional basado en arquitectura **RAG (Retrieval-Augmented Generation)** diseñado para responder consultas de forma precisa, trazable y libre de alucinaciones a partir de documentación normativa y administrativa (reglamentos, convocatorias y manuales).

---

## Arquitectura del Pipeline

El flujo de datos consta de seis etapas secuenciales desde la ingesta documental hasta la generación de respuestas citadas:

```mermaid
flowchart TD
    subgraph S1 ["1. Base documental"]
        direction TB
        A["PDF · Reglamentos · Convocatorias · Manuales"]
    end

    subgraph S2 ["2. Procesamiento y fragmentación"]
        direction TB
        B["Extracción · Limpieza · Chunking · Metadata"]
    end

    subgraph S3 ["3. Representación vectorial"]
        direction TB
        C["BGE-M3 · Embeddings de 1024 dimensiones"]
    end

    subgraph S4 ["4. Recuperación de información"]
        direction TB
        D["ChromaDB · Búsqueda semántica · Top-K"]
    end

    subgraph S5 ["5. Generación de respuestas"]
        direction TB
        E["Qwen 2.5 3B · Prompt de control · Contexto recuperado"]
    end

    subgraph S6 ["6. Respuesta fundamentada"]
        direction TB
        F["Respuesta · Referencias · Documento · Página"]
    end

    S1 --> S2 --> S3 --> S4 --> S5 --> S6

    style S1 fill:#eef2ff,stroke:#c7d2fe,color:#1e293b
    style S2 fill:#eef2ff,stroke:#c7d2fe,color:#1e293b
    style S3 fill:#eef2ff,stroke:#c7d2fe,color:#1e293b
    style S4 fill:#eef2ff,stroke:#c7d2fe,color:#1e293b
    style S5 fill:#eef2ff,stroke:#c7d2fe,color:#1e293b
    style S6 fill:#ecfdf5,stroke:#a7f3d0,color:#064e3b

    style A fill:#ffffff,stroke:none,color:#475569
    style B fill:#ffffff,stroke:none,color:#475569
    style C fill:#ffffff,stroke:none,color:#475569
    style D fill:#ffffff,stroke:none,color:#475569
    style E fill:#ffffff,stroke:none,color:#475569
    style F fill:#ffffff,stroke:none,color:#065f46
```

## Descripción técnica por etapas
1. Ingesta de la base documental:
Se cargan las fuentes (archivos en formato PDF) correspondientes a reglamentos, convocatorias y manuales. El objetivo es centralizar el corpus de conocimiento oficial que servirá como única fuente de verdad para el modelo

2. Procesamiento y fragmentación
Extracción y limpieza de todo el texto plano, eliminando encabezados, caracteres corruptos y ruido tipográfico. En esta etapa se realiza un proceso de chunking (fragmentación / segmentación) de los documentos con un ligero solapamiento para preservar la continuidad semántica de los bloques.
Adicionalmente cada fragmento es etiquetado con su documento de origen y no. de página para garantizar la trazabilidad posterior. 
