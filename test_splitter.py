
from src.document_loader import load_documents
from src.text_splitter import DocumentSplitter


# 1. Extraer documentos
documents = load_documents("data/documentos")

# 2. Configurar fragmentador
splitter = DocumentSplitter(
    chunk_size=2000,
    chunk_overlap=400
)

# 3. Generar fragmentos
chunks = splitter.split_documents(documents)

print("\n" + "=" * 55)
print("RESULTADOS DE FRAGMENTACIÓN")
print("=" * 55)

print(f"Total de páginas: {len(documents)}")
print(f"Total de chunks: {len(chunks)}")

# 4. Mostrar los primeros cinco fragmentos
for i, chunk in enumerate(chunks[:5]):

    print(f"\n{'=' * 55}")
    print(f"CHUNK {i + 1}")
    print("=" * 55)

    print("Documento:",
          chunk["metadata"]["source"])

    print("Página:",
          chunk["metadata"]["page"])

    print("Identificador:",
          chunk["metadata"]["chunk_id"])

    print("Caracteres:",
          len(chunk["text"]))

    print("\nContenido:")
    print(chunk["text"][:700])
