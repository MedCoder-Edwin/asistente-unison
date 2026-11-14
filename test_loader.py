
from src.document_loader import load_documents

# Directorio de documentos
DATA_PATH = "data/documentos"

# Procesar documentos
documents = load_documents(DATA_PATH)

print("\n" + "=" * 50)
print("RESULTADOS DE LA EXTRACCIÓN")
print("=" * 50)

print(f"Total de páginas procesadas: {len(documents)}")

if documents:

    for i, document in enumerate(documents[:3]):

        print(f"\n--- DOCUMENTO {i + 1} ---")

        print("Archivo:",
              document["metadata"]["source"])

        print("Página:",
              document["metadata"]["page"])

        print("Categoría:",
              document["metadata"]["category"])

        print("\nContenido:")
        print(document["text"][:500])

else:
    print("No se obtuvo contenido.")
