
import re
import logging
from typing import List, Dict


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


class DocumentSplitter:

    def __init__(
        self,
        chunk_size: int = 2000,
        chunk_overlap: int = 400
    ):

        if chunk_size <= 0:
            raise ValueError("chunk_size debe ser positivo.")

        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap debe ser menor que chunk_size."
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_paragraphs(self, text: str) -> List[str]:
        """
        Divide el texto utilizando los saltos de línea
        como separadores de párrafos.
        """

        paragraphs = re.split(r"\n\s*\n", text)

        return [
            paragraph.strip()
            for paragraph in paragraphs
            if paragraph.strip()
        ]

    def split_long_paragraph(self, paragraph: str) -> List[str]:
        """
        Divide párrafos demasiado extensos.
        Prioriza oraciones completas.
        """

        if len(paragraph) <= self.chunk_size:
            return [paragraph]

        sentences = re.split(
            r'(?<=[.!?])\s+',
            paragraph
        )

        pieces = []
        current = ""

        for sentence in sentences:

            if len(sentence) > self.chunk_size:

                if current:
                    pieces.append(current.strip())
                    current = ""

                # Dividir por palabras cuando una oración
                # supera el tamaño permitido.
                words = sentence.split()
                part = ""

                for word in words:

                    candidate = (
                        f"{part} {word}".strip()
                    )

                    if len(candidate) > self.chunk_size:

                        if part:
                            pieces.append(part.strip())

                        part = word

                    else:
                        part = candidate

                if part:
                    current = part

            else:

                candidate = (
                    f"{current} {sentence}".strip()
                )

                if len(candidate) > self.chunk_size:

                    if current:
                        pieces.append(current.strip())

                    current = sentence

                else:
                    current = candidate

        if current:
            pieces.append(current.strip())

        return pieces


    def split_page(self, text: str) -> List[str]:
        """
        Genera fragmentos de una página respetando
        el tamaño máximo y el solapamiento configurado.
        """

        paragraphs = self.split_paragraphs(text)

        expanded_paragraphs = []

        for paragraph in paragraphs:
            expanded_paragraphs.extend(
                self.split_long_paragraph(paragraph)
            )

        chunks = []
        current_chunk = ""

        for paragraph in expanded_paragraphs:

            separator = "\n\n" if current_chunk else ""

            candidate = current_chunk + separator + paragraph

            if len(candidate) <= self.chunk_size:
                current_chunk = candidate
                continue

            # Guardar el fragmento actual
            if current_chunk:
                chunks.append(current_chunk.strip())

            # Calcular el solapamiento sin exceder
            # el tamaño máximo del siguiente fragmento.
            available_overlap = max(
                0,
                self.chunk_size - len(paragraph) - 2
            )

            overlap_size = min(
                self.chunk_overlap,
                available_overlap,
                len(current_chunk)
            )

            overlap = (
                current_chunk[-overlap_size:].strip()
                if overlap_size > 0 else ""
            )

            # Construir el siguiente fragmento
            if overlap:
                current_chunk = overlap + "\n\n" + paragraph
            else:
                current_chunk = paragraph

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks


    def split_documents(
        self,
        documents: List[Dict]
    ) -> List[Dict]:
        """
        Procesa las páginas extraídas y genera
        fragmentos con sus metadatos originales.
        """

        all_chunks = []

        for document in documents:

            text = document["text"]
            metadata = document["metadata"]

            page_chunks = self.split_page(text)

            for index, chunk_text in enumerate(
                page_chunks
            ):

                chunk = {
                    "text": chunk_text,
                    "metadata": {
                        **metadata,
                        "chunk_index": index,
                        "chunk_id": (
                            f"{metadata['source']}_"
                            f"p{metadata['page']}_"
                            f"c{index}"
                        )
                    }
                }

                all_chunks.append(chunk)

        logger.info(
            f"Total de fragmentos generados: "
            f"{len(all_chunks)}"
        )

        return all_chunks
