
from src.rag_pipeline import RAGPipeline


def main():

    rag = RAGPipeline(
        #model="qwen2.5:3b-instruct",
        #model="qwen3:4b-instruct-2507-q4_K_M",
        model="gemma3:4b",
        top_k=5
    )

    question = (
        "¿Qué documentos debo presentar para liberar mi servicio social?"
    )

    print("\n" + "=" * 60)
    print("ASISTENTE VIRTUAL UNISON")
    print("=" * 60)

    print("\nPregunta:")
    print(question)

    result = rag.ask(question)

    print("\n" + "=" * 60)
    print("RESPUESTA GENERADA")
    print("=" * 60)

    print(result["answer"])

    print("\n" + "=" * 60)
    print("FUENTES RECUPERADAS")
    print("=" * 60)

    for source in result["sources"]:
        print(
            f"- {source['document']} | "
            f"Página: {source['page']}"
        )

    t = result["timings"]

    print("\n" + "=" * 60)
    print("TIEMPOS")
    print("=" * 60)
    print(f"Retrieval (embedding + búsqueda): {t['retrieval_s']:.2f} s")
    print(f"Generación (LLM):                 {t['generation_s']:.2f} s")
    print(f"Total:                            {t['total_s']:.2f} s")
    print(f"Carga del modelo en Ollama:       {t['model_load_s']:.2f} s")
    print(f"Tokens de entrada (prompt):       {t['prompt_tokens']}")
    print(f"Tokens generados:                 {t['output_tokens']}")
    print(f"Velocidad de generación:          {t['tokens_per_s']:.1f} tokens/s")


if __name__ == "__main__":
    main()
