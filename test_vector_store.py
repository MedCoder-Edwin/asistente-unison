
from src.document_loader import load_documents
from src.text_splitter import DocumentSplitter
from src.embeddings import EmbeddingGenerator
from src.vector_store import VectorStore


# ==========================================
# 1. EXTRAER DOCUMENTOS
# ==========================================

print("\n1. Extrayendo documentos...")

documents = load_documents("data/documentos")


# ==========================================
# 2. FRAGMENTAR DOCUMENTOS
# ==========================================

print("\n2. Generando fragmentos...")

splitter = DocumentSplitter(
    chunk_size=2000,
    chunk_overlap=400
)

chunks = splitter.split_documents(documents)


# ==========================================
# 3. GENERAR EMBEDDINGS
# ==========================================

print("\n3. Generando embeddings...")

generator = EmbeddingGenerator(
    model="bge-m3",
    batch_size=16
)

embedded_documents = generator.embed_documents(chunks)


# ==========================================
# 4. ALMACENAR EN CHROMADB
# ==========================================

print("\n4. Almacenando en ChromaDB...")

vector_store = VectorStore(
    persist_directory="data/chroma_db",
    collection_name="unison_documents"
)

vector_store.add_documents(embedded_documents)


# ==========================================
# 5. VERIFICAR RESULTADOS
# ==========================================

print("\n" + "=" * 50)
print("RESULTADOS DE INDEXACIÓN")
print("=" * 50)

print(
    "Total de fragmentos generados:",
    len(chunks)
)

print(
    "Total de registros en ChromaDB:",
    vector_store.count()
)

print("\nIndexación completada.")
