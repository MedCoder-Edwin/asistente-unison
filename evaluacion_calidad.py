"""Evaluación de CALIDAD del Asistente Unison.

¿Qué hace?
  Hace las preguntas de preguntas_evaluacion.json (que tienen respuesta
  conocida) y revisa, para cada configuración del asistente:
    1. Recuperación: ¿encontró el documento y la página correctos?
    2. Citas:        ¿citó el documento correcto en su respuesta?
    3. Respuesta:    ¿contiene los datos clave esperados (ej. "480 horas")?
    4. Abstención:   en preguntas que NO están en los documentos,
                     ¿dijo "no encontré información" en lugar de inventar?

¿Cómo se usa?
  1. Ollama abierto. NO hace falta correr app.py (mejor apágalo para que
     no compita por la GPU).
  2. Desde la carpeta del proyecto:
        .\\.venv\\Scripts\\python.exe evaluacion_calidad.py
  3. Tarda aprox. 30-40 minutos (23 preguntas x 2 configuraciones).

¿Qué entrega?
  - Tabla resumen en la terminal.
  - evaluacion_detalle.csv: cada pregunta, la respuesta completa y si acertó
    (para revisar a mano las respuestas dudosas).
  - evaluacion_resumen.csv: las métricas por configuración (para el informe).
"""
import csv
import json
import logging
import os
import re
import time
import unicodedata
from pathlib import Path

# Trabajar siempre desde la carpeta del proyecto (ChromaDB usa rutas relativas)
os.chdir(Path(__file__).resolve().parent)

from src.rag_pipeline_v2 import ABSTENTION, RAGPipeline  # noqa: E402

logging.getLogger().setLevel(logging.WARNING)  # menos mensajes en pantalla

# ==========================================
# CONFIGURACIÓN
# ==========================================

# Configuraciones a comparar. Solo cambia la reformulación de la pregunta;
# lo demás es igual a lo que usa app.py.
CONFIGURACIONES = [
    {"nombre": "con_reformulacion", "expand_queries": True},
    {"nombre": "sin_reformulacion", "expand_queries": False},
]

ARCHIVO_PREGUNTAS = "preguntas_evaluacion.json"
TOLERANCIA_PAGINA = 1  # se acepta la página esperada +-1 (un artículo puede cruzar páginas)


# ==========================================
# FUNCIONES DE APOYO
# ==========================================

def normalizar(texto):
    """Minúsculas y sin acentos, para comparar textos sin fallar por una tilde."""
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def contiene_dato(respuesta, clave):
    """¿La respuesta contiene el dato clave? 'seis meses|6 meses' acepta cualquiera."""
    texto = normalizar(respuesta)
    for opcion in clave.split("|"):
        opcion = normalizar(opcion).strip()
        # Para números exigimos que no sean parte de otro número (ej. '5' en '50')
        if re.fullmatch(r"[\d.]+", opcion):
            if re.search(rf"(?<![\d.]){re.escape(opcion)}(?![\d])", texto):
                return True
        elif opcion in texto:
            return True
    return False


def coincide(fuente, esperado):
    """¿Una fuente (documento + página) coincide con la esperada?"""
    doc_ok = normalizar(esperado["documento"]) in normalizar(fuente.get("document"))
    pagina = fuente.get("page")
    pag_ok = (
        doc_ok
        and isinstance(pagina, int)
        and abs(pagina - esperado["pagina"]) <= TOLERANCIA_PAGINA
    )
    return doc_ok, pag_ok


def evaluar_pregunta(pipeline, p):
    """Hace una pregunta y calcula si cada aspecto fue correcto."""
    inicio = time.perf_counter()
    try:
        resultado = pipeline.ask(p["pregunta"])
        error = ""
    except Exception as e:  # si Ollama falla, se registra y se sigue
        resultado, error = {"answer": "", "sources": [], "citation_check": {}}, str(e)
    latencia = time.perf_counter() - inicio

    respuesta = resultado.get("answer", "")
    fuentes = resultado.get("sources", [])
    citas = resultado.get("citation_check", {}).get("citation_details", [])
    se_abstuvo = respuesta.strip() == ABSTENTION or not respuesta.strip()

    fila = {
        "id": p["id"],
        "tipo": p["tipo"],
        "pregunta": p["pregunta"],
        "respuesta": respuesta,
        "se_abstuvo": se_abstuvo,
        "latencia_s": round(latencia, 1),
        "error": error,
    }

    if p["tipo"] == "respondible":
        # Recuperación: ¿entre las fuentes recuperadas está el documento/página esperados?
        fila["recupero_documento"] = any(coincide(f, p)[0] for f in fuentes)
        fila["recupero_pagina"] = any(coincide(f, p)[1] for f in fuentes)
        # Cita: ¿la respuesta cita el documento esperado?
        fila["cita_correcta"] = any(coincide(c, p)[0] for c in citas)
        # Datos clave: cuántos de los esperados aparecen en la respuesta
        encontrados = [c for c in p["palabras_clave"] if contiene_dato(respuesta, c)]
        fila["datos_clave"] = f"{len(encontrados)}/{len(p['palabras_clave'])}"
        fila["respuesta_correcta"] = (
            not se_abstuvo and len(encontrados) == len(p["palabras_clave"])
        )
        fila["comportamiento_correcto"] = fila["respuesta_correcta"]
    else:
        # Pregunta fuera de los documentos: lo correcto es abstenerse
        fila["comportamiento_correcto"] = se_abstuvo

    return fila


def porcentaje(filas, campo):
    """Porcentaje de filas donde el campo es verdadero."""
    if not filas:
        return 0.0
    return round(100 * sum(1 for f in filas if f.get(campo)) / len(filas), 1)


# ==========================================
# PROGRAMA PRINCIPAL
# ==========================================

def main():
    preguntas = json.loads(Path(ARCHIVO_PREGUNTAS).read_text(encoding="utf-8"))
    print(f"{len(preguntas)} preguntas cargadas de {ARCHIVO_PREGUNTAS}")

    detalle, resumen = [], []

    for config in CONFIGURACIONES:
        print(f"\n=== Configuración: {config['nombre']} ===")
        pipeline = RAGPipeline(
            retrieval_mode="semantic_continuation",
            expand_queries=config["expand_queries"],
            select_passages=True,
        )
        pipeline.ask("¿Qué es el servicio social?")  # calentamiento (no se mide)

        filas = []
        for p in preguntas:
            fila = evaluar_pregunta(pipeline, p)
            fila["configuracion"] = config["nombre"]
            filas.append(fila)
            marca = "OK " if fila["comportamiento_correcto"] else "MAL"
            print(f"  [{marca}] #{p['id']:>2} ({fila['latencia_s']:>5.1f} s) {p['pregunta'][:60]}")
        detalle.extend(filas)

        # Métricas de esta configuración
        resp = [f for f in filas if f["tipo"] == "respondible"]
        fuera = [f for f in filas if f["tipo"] == "fuera_de_alcance"]
        resumen.append({
            "configuracion": config["nombre"],
            "recuperacion_documento_%": porcentaje(resp, "recupero_documento"),
            "recuperacion_pagina_%": porcentaje(resp, "recupero_pagina"),
            "cita_correcta_%": porcentaje(resp, "cita_correcta"),
            "respuesta_correcta_%": porcentaje(resp, "respuesta_correcta"),
            # Se abstuvo aunque la respuesta SÍ estaba en los documentos
            "abstencion_indebida_%": porcentaje(resp, "se_abstuvo"),
            # Se abstuvo correctamente en preguntas fuera de los documentos
            "abstencion_correcta_%": porcentaje(fuera, "se_abstuvo"),
            "latencia_promedio_s": round(sum(f["latencia_s"] for f in filas) / len(filas), 1),
        })

    # Guardar resultados (encoding utf-8-sig para que Excel muestre bien los acentos)
    campos = ["configuracion", "id", "tipo", "pregunta", "respuesta", "se_abstuvo",
              "recupero_documento", "recupero_pagina", "cita_correcta", "datos_clave",
              "respuesta_correcta", "comportamiento_correcto", "latencia_s", "error"]
    with open("evaluacion_detalle.csv", "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(detalle)
    with open("evaluacion_resumen.csv", "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=list(resumen[0].keys()))
        escritor.writeheader()
        escritor.writerows(resumen)

    # Tabla resumen en pantalla
    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)
    for r in resumen:
        print(f"\n{r['configuracion']}")
        for clave, valor in r.items():
            if clave != "configuracion":
                print(f"  {clave:<28} {valor}")
    print("\nDetalle en evaluacion_detalle.csv | resumen en evaluacion_resumen.csv")


if __name__ == "__main__":
    main()
