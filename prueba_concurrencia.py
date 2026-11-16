"""Prueba de concurrencia del Asistente Unison.

¿Qué hace?
  Simula varios usuarios haciendo preguntas AL MISMO TIEMPO y mide
  cuánto tarda cada uno en recibir su respuesta.

¿Cómo se usa?
  1. En una terminal, arranca el asistente:   python app.py
  2. En OTRA terminal, corre esta prueba:      python prueba_concurrencia.py
     (Opcional) probar contra otra PC:         python prueba_concurrencia.py http://192.168.1.50:8765

¿Qué entrega?
  - Una tabla resumen en la terminal.
  - El archivo resultados_concurrencia.csv con cada pregunta medida
    (para hacer gráficas en el informe).

Solo usa librerías que ya vienen con Python: no hay que instalar nada.
"""
import csv
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from statistics import mean

# ==========================================
# CONFIGURACIÓN (puedes cambiar estos valores)
# ==========================================

# Dirección del asistente (se puede pasar como argumento al correr el script)
URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765").rstrip("/")

# Cuántos usuarios simultáneos probar en cada nivel
NIVELES = [1, 3, 5]

# Cuántas veces se repite cada nivel (más repeticiones = promedio más confiable)
REPETICIONES = 2

# Tiempo máximo de espera por respuesta, en segundos
TIMEOUT = 900

# Preguntas de prueba: cada usuario simulado toma una distinta
PREGUNTAS = [
    "¿Qué requisitos debo cumplir para hacer el servicio social?",
    "¿Qué tipos de becas estudiantiles existen?",
    "¿Cómo funcionan las prácticas profesionales?",
    "¿Cuántas veces puedo inscribirme en una misma materia?",
    "¿Qué requisitos hay para participar en movilidad estudiantil?",
    "¿Cuál es el plazo para obtener el grado de maestría?",
    "¿Cuánto cuesta expedir un certificado de estudios?",
    "¿Quién nombra al rector de la universidad?",
    "¿Qué es una beca de ayudantía?",
    "¿Cuándo se considera que un alumno causa baja?",
]

ARCHIVO_CSV = "resultados_concurrencia.csv"


# ==========================================
# FUNCIONES
# ==========================================

def preguntar(pregunta):
    """Envía UNA pregunta al asistente y regresa (código, datos)."""
    cuerpo = json.dumps({"question": pregunta}).encode("utf-8")
    peticion = urllib.request.Request(
        f"{URL}/api/chat",
        data=cuerpo,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as respuesta:
            return respuesta.status, json.loads(respuesta.read())
    except urllib.error.HTTPError as error:      # el servidor respondió con error
        return error.code, {}
    except Exception as error:                    # no hubo conexión o se acabó el tiempo
        return 0, {"error": str(error)}


def ronda(usuarios, repeticion):
    """Lanza 'usuarios' preguntas al mismo tiempo y mide cada una."""
    resultados = []
    candado = threading.Lock()                   # evita que dos hilos escriban la lista a la vez
    salida = threading.Barrier(usuarios)         # "línea de salida": todos arrancan juntos

    def usuario(numero):
        pregunta = PREGUNTAS[(numero + repeticion * usuarios) % len(PREGUNTAS)]
        salida.wait()                            # espera a que todos estén listos
        inicio = time.perf_counter()
        codigo, datos = preguntar(pregunta)
        latencia = time.perf_counter() - inicio
        tiempos = datos.get("timings", {}) if isinstance(datos, dict) else {}
        with candado:
            resultados.append({
                "usuarios_simultaneos": usuarios,
                "repeticion": repeticion + 1,
                "usuario": numero + 1,
                "pregunta": pregunta,
                "codigo_http": codigo,
                "exito": codigo == 200,
                "latencia_s": round(latencia, 2),
                "busqueda_s": round(tiempos.get("retrieval_s", 0), 2),
                "generacion_s": round(tiempos.get("generation_s", 0), 2),
            })

    # Un hilo por usuario simulado
    hilos = [threading.Thread(target=usuario, args=(i,)) for i in range(usuarios)]
    inicio_ronda = time.perf_counter()
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()                                 # espera a que todos terminen
    duracion_ronda = time.perf_counter() - inicio_ronda
    return resultados, duracion_ronda


# ==========================================
# PROGRAMA PRINCIPAL
# ==========================================

def main():
    print(f"Probando el asistente en {URL}")

    # Calentamiento: la primera pregunta carga los modelos en memoria.
    # No se cuenta para no "ensuciar" las mediciones.
    print("Calentando el modelo (esta pregunta no se mide)...")
    codigo, datos = preguntar("¿Qué es el servicio social?")
    if codigo != 200:
        print(f"El asistente no respondió (código {codigo}). ¿Está corriendo app.py y Ollama?")
        print(datos)
        return

    todos = []
    resumen = []

    for usuarios in NIVELES:
        for rep in range(REPETICIONES):
            print(f"\n> {usuarios} usuario(s) simultáneo(s), repetición {rep + 1}/{REPETICIONES}...")
            resultados, duracion = ronda(usuarios, rep)
            todos.extend(resultados)
            exitos = [r for r in resultados if r["exito"]]
            print(f"  Terminó en {duracion:.1f} s | respuestas correctas: {len(exitos)}/{usuarios}")
            resumen.append((usuarios, duracion, resultados))

    # Guardar cada medición en CSV (se abre en Excel o con pandas)
    with open(ARCHIVO_CSV, "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=list(todos[0].keys()))
        escritor.writeheader()
        escritor.writerows(todos)

    # Tabla resumen por nivel de usuarios
    print("\n" + "=" * 72)
    print("RESUMEN")
    print("=" * 72)
    print(f"{'Usuarios':>8} | {'Latencia prom (s)':>17} | {'Latencia máx (s)':>16} | {'Errores':>7} | {'Preguntas/min':>13}")
    print("-" * 72)
    for usuarios in NIVELES:
        filas = [r for r in todos if r["usuarios_simultaneos"] == usuarios]
        ok = [r["latencia_s"] for r in filas if r["exito"]]
        errores = len(filas) - len(ok)
        duraciones = [d for u, d, _ in resumen if u == usuarios]
        # Preguntas por minuto = cuántas respuestas salen en un minuto con esa carga
        por_minuto = len(ok) / sum(duraciones) * 60 if duraciones else 0
        prom = f"{mean(ok):.1f}" if ok else "-"
        maxi = f"{max(ok):.1f}" if ok else "-"
        print(f"{usuarios:>8} | {prom:>17} | {maxi:>16} | {errores:>7} | {por_minuto:>13.1f}")

    print(f"\nDetalle guardado en {ARCHIVO_CSV} ({datetime.now():%Y-%m-%d %H:%M})")


if __name__ == "__main__":
    main()
