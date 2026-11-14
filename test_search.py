
from src.embeddings import EmbeddingGenerator
from src.vector_store import VectorStore


# Inicializar componentes
generator = EmbeddingGenerator(
    model="bge-m3"
)

vector_store = VectorStore(
    persist_directory="data/chroma_db",
    collection_name="unison_documents"
)


# Pregunta del usuario
question = (
    "¿Qué requisitos debe cumplir un estudiante de la "
    "Universidad de Sonora antes de iniciar su servicio social?"
)


print("\nPregunta:")
print(question)


# Generar embedding de la pregunta
query_embedding = generator.generate_embeddings(
    [question]
)[0]


# Buscar los cinco fragmentos más relevantes
results = vector_store.search(
    query_embedding=query_embedding,
    n_results=10
)


# Mostrar resultados
print("\n" + "=" * 60)
print("RESULTADOS DE BÚSQUEDA SEMÁNTICA")
print("=" * 60)


for i, result in enumerate(results):

    metadata = result["metadata"]

    print(f"\nRESULTADO {i + 1}")
    print("-" * 50)

    print("Documento:", metadata["source"])
    print("Página:", metadata["page"])
    print("Distancia:", round(result["distance"], 4))

    print("\nContenido:")
    print(result["text"][:700])
