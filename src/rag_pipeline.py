import time
import logging
import requests

from src.embeddings import EmbeddingGenerator
from src.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RAGPipeline:

    def __init__(
        self,
        model="qwen2.5:7b-instruct",
        ollama_url="http://localhost:11434",
        top_k=10
    ):
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self.top_k = top_k

        self.embedding_generator = EmbeddingGenerator(
            model="bge-m3"
        )

        self.vector_store = VectorStore(
            persist_directory="data/chroma_db",
            collection_name="unison_documents"
        )

    def retrieve_context(self, question):
        """Recupera los fragmentos relevantes de ChromaDB."""

        query_embedding = (
            self.embedding_generator.generate_embeddings(
                [question]
            )[0]
        )

        results = self.vector_store.search(
            query_embedding=query_embedding,
            n_results=self.top_k
        )

        return results

    def build_context(self, results):
        """Construye el contexto incluyendo referencias."""

        context_parts = []

        for index, result in enumerate(results, start=1):

            metadata = result["metadata"]

            source = metadata.get("source", "Documento desconocido")
            page = metadata.get("page", "Desconocida")

            context_parts.append(
                f"""
[FRAGMENTO {index}]
Documento: {source}
Página: {page}

Contenido:
{result["text"]}
"""
            )

        return "\n".join(context_parts)

    def generate_answer(self, question, context):
        """Genera una respuesta utilizando Qwen mediante Ollama."""


        system_prompt = """
        Eres un asistente virtual especializado en los reglamentos,
        procedimientos y documentos institucionales de la Universidad
        de Sonora.

        Tu función es responder preguntas de estudiantes y profesores
        utilizando exclusivamente la información del contexto documental.

        REGLAS OBLIGATORIAS:

        1. Responde únicamente con información explícita en el contexto.

        2. No inventes requisitos, fechas, cantidades, excepciones,
        recomendaciones ni procedimientos.

        3. No agregues conclusiones generales que no estén respaldadas
        por los documentos.

        4. Distingue entre requisitos para iniciar, condiciones durante
        un procedimiento y requisitos para concluirlo.

        5. Si un artículo menciona una excepción o condición especial,
        explica exactamente a quién aplica.

        6. Si el contexto no contiene información suficiente, indícalo.
        No completes la respuesta utilizando conocimientos externos.

        7. Cada afirmación importante debe incluir su referencia:
        nombre del documento, artículo y página cuando estén
        disponibles.

        8. No atribuyas información a un artículo si su contenido
        no aparece en el contexto.

        9. Si existen diferencias entre documentos, identifícalas
        sin mezclarlas.

        FORMATO DE RESPUESTA:

        - Respuesta directa.
        - Lista de requisitos o condiciones cuando corresponda.
        - Aclaraciones importantes.
        - Referencias documentales.

        Si no existe evidencia suficiente, responde:
        "No encontré información suficiente en los documentos
        proporcionados para responder esta pregunta."
        """


        user_prompt = f"""
CONTEXTO DOCUMENTAL:

{context}

PREGUNTA DEL USUARIO:

{question}

Redacta una respuesta clara, precisa y fundamentada.
Incluye las referencias documentales correspondientes.
"""

        response = requests.post(
            f"{self.ollama_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False,
                "keep_alive": "30m",
                "options": {
                    "temperature": 0.2,
                    "num_ctx": 8192
                }
            },
            timeout=180
        )

        if not response.ok:
            print("\nERROR DEVUELTO POR OLLAMA:")
            print(response.text)
            response.raise_for_status()

        data = response.json()

        # Ollama reporta las duraciones en nanosegundos
        ns = 1e9
        eval_count = data.get("eval_count", 0)
        eval_duration = data.get("eval_duration", 0) / ns

        stats = {
            "model_load_s": data.get("load_duration", 0) / ns,
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "prompt_eval_s": data.get("prompt_eval_duration", 0) / ns,
            "output_tokens": eval_count,
            "output_eval_s": eval_duration,
            "tokens_per_s": (eval_count / eval_duration) if eval_duration else 0,
            "ollama_total_s": data.get("total_duration", 0) / ns,
        }

        return data["message"]["content"], stats

    def ask(self, question):
        """Ejecuta el flujo completo RAG."""

        if not question.strip():
            raise ValueError("La pregunta no puede estar vacía.")

        t_start = time.perf_counter()

        logger.info("Recuperando información documental...")

        t0 = time.perf_counter()
        results = self.retrieve_context(question)
        t_retrieval = time.perf_counter() - t0

        if not results:
            return {
                "answer": (
                    "No encontré información suficiente en los "
                    "documentos proporcionados para responder "
                    "esta pregunta."
                ),
                "sources": [],
                "retrieved_documents": [],
                "timings": {"retrieval_s": t_retrieval}
            }

        context = self.build_context(results)

        logger.info("Generando respuesta con Qwen...")

        t1 = time.perf_counter()
        answer, llm_stats = self.generate_answer(question, context)
        t_generation = time.perf_counter() - t1

        sources = []
        for result in results:
            metadata = result["metadata"]
            source = {
                "document": metadata.get("source"),
                "page": metadata.get("page")
            }
            if source not in sources:
                sources.append(source)

        return {
            "answer": answer,
            "sources": sources,
            "retrieved_documents": results,
            "timings": {
                "retrieval_s": t_retrieval,
                "generation_s": t_generation,
                "total_s": time.perf_counter() - t_start,
                **llm_stats,
            }
        }