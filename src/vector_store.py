
import chromadb
import logging

from typing import List, Dict


logger = logging.getLogger(__name__)


class VectorStore:

    def __init__(
        self,
        persist_directory: str = "data/chroma_db",
        collection_name: str = "unison_documents"
    ):

        # Cliente persistente
        self.client = chromadb.PersistentClient(
            path=persist_directory
        )

        # Crear u obtener colección
        self.collection = (
            self.client.get_or_create_collection(
                name=collection_name,
                metadata={
                    "hnsw:space": "cosine"
                }
            )
        )

        logger.info(
            f"Base vectorial inicializada: "
            f"{collection_name}"
        )

    def add_documents(
        self,
        documents: List[Dict],
        batch_size: int = 50
    ):
        """
        Almacena documentos y embeddings en ChromaDB.

        Utiliza upsert para insertar o actualizar
        registros sin duplicar sus identificadores.
        """

        if not documents:
            logger.warning("No hay documentos para almacenar.")
            return

        for start in range(0, len(documents), batch_size):

            batch = documents[
                start:start + batch_size
            ]

            ids = []
            texts = []
            embeddings = []
            metadatas = []

            for document in batch:

                ids.append(
                    document["metadata"]["chunk_id"]
                )

                texts.append(
                    document["text"]
                )

                embeddings.append(
                    document["embedding"]
                )

                metadatas.append(
                    document["metadata"]
                )

            self.collection.upsert(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas
            )

            logger.info(
                f"Registros almacenados: "
                f"{min(start + batch_size, len(documents))}"
                f"/{len(documents)}"
            )

        logger.info(
            f"Total de registros en ChromaDB: "
            f"{self.collection.count()}"
        )

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Dict = None
    ) -> List[Dict]:
        """
        Busca los fragmentos más cercanos
        al embedding de una consulta.

        Args:
            query_embedding: Vector de la pregunta.
            n_results: Número de resultados.
            where: Filtros opcionales de metadatos.

        Returns:
            Lista de documentos relevantes.
        """

        if not query_embedding:
            raise ValueError("El embedding está vacío.")

        total = self.collection.count()

        if total == 0:
            logger.warning("La colección está vacía.")
            return []

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, total),
            where=where,
            include=[
                "documents",
                "metadatas",
                "distances"
            ]
        )

        documents = []

        for i in range(len(results["ids"][0])):

            documents.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            })

        return documents

    def count(self) -> int:
        """
        Devuelve el número de registros almacenados.
        """

        return self.collection.count()
