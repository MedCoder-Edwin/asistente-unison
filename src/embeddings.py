#Transforma los fragmentos de texto en representaciones
#vectoriales 


import requests
import logging
from typing import List, Dict


logger = logging.getLogger(__name__)


class EmbeddingGenerator:

    def __init__(
        self,
        model: str = "bge-m3",
        base_url: str = "http://localhost:11434",
        batch_size: int = 16
    ):

        self.model = model
        self.url = f"{base_url}/api/embed"
        self.batch_size = batch_size

        self.session = requests.Session()

    def generate_embeddings(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        """
        Genera embeddings para una lista de textos.
        Procesa los textos por lotes.
        """

        if not texts:
            return []

        all_embeddings = []

        for start in range(0, len(texts), self.batch_size):

            batch = texts[
                start:start + self.batch_size
            ]

            payload = {
                "model": self.model,
                "input": batch
            }

            try:

                response = self.session.post(
                    self.url,
                    json=payload,
                    timeout=300
                )

                response.raise_for_status()

                result = response.json()

                embeddings = result.get("embeddings", [])

                if len(embeddings) != len(batch):
                    raise ValueError(
                        "La cantidad de embeddings no coincide "
                        "con la cantidad de textos."
                    )

                all_embeddings.extend(embeddings)

                logger.info(
                    f"Embeddings generados: "
                    f"{len(all_embeddings)}/{len(texts)}"
                )

            except requests.RequestException as error:

                logger.error(
                    f"Error de comunicación con Ollama: {error}"
                )

                raise

        return all_embeddings

    def embed_documents(
        self,
        documents: List[Dict]
    ) -> List[Dict]:
        """
        Genera embeddings y los asocia con sus
        respectivos textos y metadatos.
        """

        if not documents:
            return []

        texts = [
            document["text"]
            for document in documents
        ]

        embeddings = self.generate_embeddings(texts)

        results = []

        for document, embedding in zip(
            documents,
            embeddings
        ):

            results.append({
                "text": document["text"],
                "metadata": document["metadata"],
                "embedding": embedding
            })

        logger.info(
            f"Proceso finalizado: {len(results)} embeddings."
        )

        return results
