"""Interfaz local para el asistente documental de la Unison.

Versión con soporte para VARIOS USUARIOS A LA VEZ (concurrencia).

Cambios respecto a la versión anterior:
  1. ThreadingHTTPServer: cada visita se atiende en su propio "hilo"
     (como tener varios meseros en lugar de uno).
  2. Escucha en 0.0.0.0: acepta conexiones de otros dispositivos
     de la misma red (celulares, otras laptops), no solo de esta PC.
  3. El "cerebro" (RAGPipeline) se carga UNA vez al arrancar,
     antes de recibir visitas, para que dos usuarios no lo creen al mismo tiempo.
  4. Cada respuesta incluye los tiempos medidos, para el script de pruebas.

Configuración opcional con variables de entorno:
  HOST  -> dirección donde escucha (por defecto 0.0.0.0 = toda la red)
  PORT  -> puerto (por defecto 8765)
"""
import json
import logging
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Archivos de la página web que el servidor puede entregar
ASSETS = {
    "/": ("index.html", "text/html"),
    "/style.css": ("style.css", "text/css"),
    "/chat.js": ("chat.js", "text/javascript"),
}

# Lee HOST y PORT del sistema; si no existen, usa los valores por defecto
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8765"))


class ChatHandler(BaseHTTPRequestHandler):
    # El pipeline se comparte entre todos los usuarios (se crea una sola vez en main)
    pipeline = None

    def send_content(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, data):
        self.send_content(status, json.dumps(data, ensure_ascii=False).encode(), "application/json")

    def do_GET(self):
        # Entrega la página (HTML, CSS o JS) que pide el navegador
        asset = ASSETS.get(self.path)
        if asset is None:
            self.send_error(404)
            return
        name, content_type = asset
        self.send_content(200, (ROOT / "web" / name).read_bytes(), content_type)

    def do_POST(self):
        # Solo aceptamos preguntas en la ruta /api/chat
        if self.path != "/api/chat":
            self.send_error(404)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json(415, {"error": "La consulta debe enviarse en formato JSON."})
            return

        # --- Validar la pregunta (que exista y no sea demasiado larga) ---
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16_384:
                raise ValueError
            payload = json.loads(self.rfile.read(length))
            question = payload.get("question") if isinstance(payload, dict) else None
            if not isinstance(question, str) or not 0 < len(question.strip()) <= 2000:
                raise ValueError
        except ValueError:
            self.send_json(400, {"error": "Escribe una pregunta de hasta 2000 caracteres."})
            return

        # --- Preguntarle al asistente ---
        try:
            result = ChatHandler.pipeline.ask(question.strip())
            self.send_json(200, {
                "answer": result["answer"],
                "sources": result["sources"],
                "citations": result["citation_check"]["citation_details"],
                # Tiempos medidos por el pipeline (los usa prueba_concurrencia.py)
                "timings": result.get("timings", {}),
            })
        except Exception:
            logging.exception("Error al consultar el asistente")
            self.send_json(503, {"error": "No se pudo completar la consulta. Revisa Ollama y el índice de documentos e inténtalo de nuevo."})

    def log_message(self, format, *args):
        # Muestra en la terminal quién hizo cada petición (útil en la demo)
        logging.info("%s - %s", self.client_address[0], format % args)


def ip_local():
    """Averigua la IP de esta laptop en la red WiFi (para compartirla)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # no envía nada, solo elige la tarjeta de red
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def cargar_pipeline():
    """Crea el 'cerebro' una sola vez, antes de abrir el servidor."""
    from src.rag_pipeline_v2 import RAGPipeline

    pipeline = RAGPipeline(
        retrieval_mode="semantic_continuation",
        expand_queries=False,
        select_passages=True,
    )
    # Precarga la lista de fragmentos que usa la búsqueda por palabras clave.
    # Así no se construye al mismo tiempo en varios hilos con la primera visita.
    pipeline._lexical_documents()
    return pipeline


if __name__ == "__main__":
    os.chdir(ROOT)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    print("Cargando el asistente (ChromaDB y modelos)...", flush=True)
    ChatHandler.pipeline = cargar_pipeline()

    # ThreadingHTTPServer = un hilo por visita -> varios usuarios a la vez
    with ThreadingHTTPServer((HOST, PORT), ChatHandler) as server:
        server.daemon_threads = True  # los hilos se cierran solos al apagar con Ctrl+C
        print(f"Asistente Unison disponible en:", flush=True)
        print(f"  En esta laptop:        http://127.0.0.1:{PORT}", flush=True)
        if HOST == "0.0.0.0":
            print(f"  Desde otro dispositivo: http://{ip_local()}:{PORT}", flush=True)
        server.serve_forever()
