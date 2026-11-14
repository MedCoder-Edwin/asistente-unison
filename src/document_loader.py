#Modulo encargado de cargar documentos y extraer su contenido 
#conservando los metadatos necesarios para identificar el origen de cada 
#fragmento


import fitz
import re
import unicodedata
import logging

from pathlib import Path
from typing import List, Dict


# Configuración del sistema de registros
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """
    Normaliza el texto extraído de los documentos PDF.
    Conserva los saltos de línea para mantener la estructura.
    """

    # Normalización Unicode
    text = unicodedata.normalize("NFC", text)

    # Eliminar caracteres nulos y guiones suaves
    text = text.replace("\x00", "")
    text = text.replace("\u00ad", "")

    # Normalizar saltos de línea
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Limpiar espacios y tabulaciones
    text = re.sub(r"[ \t]+", " ", text)

    # Evitar demasiados saltos de línea consecutivos
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def load_pdf(pdf_path: Path) -> List[Dict]:
    """
    Extrae el contenido de un documento PDF.

    Cada página se almacena como un registro independiente,
    conservando sus metadatos.

    Returns:
        List[Dict]: Registros con texto y metadatos.
    """

    documents = []

    try:
        with fitz.open(pdf_path) as pdf:

            total_pages = len(pdf)
            pdf_metadata = pdf.metadata or {}

            logger.info(
                f"Procesando: {pdf_path.name} "
                f"({total_pages} páginas)"
            )

            for page_index, page in enumerate(pdf):

                # Extraer texto de la página
                raw_text = page.get_text("text", sort=True)

                # Limpiar contenido
                text = clean_text(raw_text)

                # Ignorar páginas sin texto extraíble
                if not text:
                    logger.warning(
                        f"Página {page_index + 1} sin texto: "
                        f"{pdf_path.name}"
                    )
                    continue

                # Crear registro estructurado
                document = {
                    "text": text,
                    "metadata": {
                        "source": pdf_path.name,
                        "source_path": str(pdf_path),
                        "page": page_index + 1,
                        "total_pages": total_pages,
                        "title": pdf_metadata.get("title") or pdf_path.stem,
                        "author": pdf_metadata.get("author") or "",
                        "category": pdf_path.parent.name
                    }
                }

                documents.append(document)

        logger.info(
            f"Extracción completada: {pdf_path.name} "
            f"({len(documents)} páginas útiles)"
        )

    except Exception as error:
        logger.error(
            f"Error procesando {pdf_path}: {error}"
        )

    return documents


def load_documents(directory: str) -> List[Dict]:
    """
    Busca y procesa todos los documentos PDF
    dentro de un directorio y sus subdirectorios.

    Args:
        directory: Ruta de la carpeta de documentos.

    Returns:
        List[Dict]: Colección de páginas extraídas.
    """

    directory_path = Path(directory)

    if not directory_path.exists():
        raise FileNotFoundError(
            f"No existe el directorio: {directory}"
        )

    if not directory_path.is_dir():
        raise NotADirectoryError(
            f"La ruta no es un directorio: {directory}"
        )

    pdf_files = sorted(
        file for file in directory_path.rglob("*")
        if file.is_file() and file.suffix.lower() == ".pdf"
    )

    if not pdf_files:
        logger.warning("No se encontraron documentos PDF.")
        return []

    logger.info(
        f"Se encontraron {len(pdf_files)} documentos PDF."
    )

    all_documents = []

    for pdf_file in pdf_files:
        documents = load_pdf(pdf_file)
        all_documents.extend(documents)

    logger.info(
        f"Total de páginas extraídas: {len(all_documents)}"
    )

    return all_documents
