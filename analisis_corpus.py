import re
import json
import hashlib
import itertools
from pathlib import Path

import pymupdf
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import chromadb

# ==========================================
# CONFIGURACIÓN
# ==========================================
DOCS_DIR = Path("data/documentos")
CHROMA_DIR = "data/chroma_db"
COLLECTION = "unison_documents"
OUT = Path("reports")
OUT.mkdir(exist_ok=True)

MIN_CHARS_TEXT = 50          # menos de esto = página sin texto útil
SIMILARITY_THRESHOLD = 0.80  # Jaccard para marcar casi-duplicados

# Si tus PDFs están en subcarpetas, la categoría es el nombre de la subcarpeta.
# Si están todos juntos, se asigna por palabras clave del nombre del archivo
# (ajusta este diccionario a tus documentos; se aplica en orden).
CATEGORY_KEYWORDS = {
    "Servicio social": ["servicio social", "servicio_social"],
    "Becas": ["beca"],
    "Convocatoria": ["convocatoria"],
    "Titulación": ["titulacion", "titulación"],
    "Movilidad": ["movilidad"],
    "Posgrado": ["posgrado"],
    "Reglamento": ["reglamento"],
    "Estatuto / Ley": ["estatuto", "ley"],
}

# Patrones de estructura
ART_RE = re.compile(r"(?im)^\s*art[ií]culo\s+\d+")
HEAD_RE = re.compile(r"(?im)^\s*(t[ií]tulo|cap[ií]tulo|secci[oó]n|transitorios?)\b.*$")
LIST_RE = re.compile(r"(?m)^\s*(?:[a-zA-Z]\)|\(?[ivxIVX]+[\).]|\d+[\).]|[-•●▪])\s+\S")


def categorize(path: Path) -> str:
    rel = path.relative_to(DOCS_DIR)
    if len(rel.parts) > 1:
        return rel.parts[0]
    name = path.stem.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(k in name for k in kws):
            return cat
    return "Otros"


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def count_upper_headers(text: str) -> int:
    n = 0
    for line in text.splitlines():
        s = line.strip()
        if 4 <= len(s) <= 80 and s.isupper() and not s.endswith(".") \
                and sum(c.isalpha() for c in s) >= 4:
            n += 1
    return n


def base_name(stem: str) -> str:
    """Nombre sin años, versiones ni marcas de copia, para agrupar versiones."""
    s = stem.lower()
    s = re.sub(r"(19|20)\d{2}", "", s)
    s = re.sub(r"\bv\s?\d+(\.\d+)*\b", "", s)
    s = re.sub(r"\(\d+\)|copia|vigente|final|actualizado|nuevo", "", s)
    return re.sub(r"[\W_]+", " ", s).strip()


def shingles(text: str, n: int = 5) -> set:
    words = text.split()
    return {" ".join(words[i:i + n]) for i in range(max(len(words) - n + 1, 1))}


# ==========================================
# 1. ANÁLISIS DE PDFs (documentos y páginas)
# ==========================================
def analyze_pdfs():
    page_rows, doc_rows, doc_texts = [], [], {}

    pdfs = sorted(DOCS_DIR.rglob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No se encontraron PDFs en {DOCS_DIR}")

    for pdf in pdfs:
        category = categorize(pdf)
        file_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
        full_text = []

        with pymupdf.open(pdf) as doc:
            for i, page in enumerate(doc, start=1):
                text = page.get_text()
                chars = len(text.strip())
                has_images = len(page.get_images()) > 0

                if chars >= MIN_CHARS_TEXT:
                    ptype = "con texto"
                elif has_images:
                    ptype = "escaneada (imagen sin texto)"
                else:
                    ptype = "vacía"

                try:
                    n_tables = len(page.find_tables().tables)
                except Exception:
                    n_tables = 0

                page_rows.append({
                    "documento": pdf.name, "categoria": category, "pagina": i,
                    "caracteres": chars, "palabras": len(text.split()),
                    "tipo_pagina": ptype, "tablas": n_tables,
                    "articulos": len(ART_RE.findall(text)),
                    "encabezados": len(HEAD_RE.findall(text)) + count_upper_headers(text),
                    "elementos_lista": len(LIST_RE.findall(text)),
                })
                full_text.append(text)

        joined = "\n".join(full_text)
        norm = normalize(joined)
        doc_texts[pdf.name] = norm
        doc_rows.append({
            "documento": pdf.name, "categoria": category,
            "paginas": len(full_text), "caracteres": len(joined),
            "palabras": len(joined.split()),
            "hash_archivo": file_hash,
            "hash_texto": hashlib.sha256(norm.encode()).hexdigest(),
            "nombre_base": base_name(pdf.stem),
            "tamano_mb": round(pdf.stat().st_size / 1e6, 2),
        })

    return pd.DataFrame(doc_rows), pd.DataFrame(page_rows), doc_texts


# ==========================================
# 2. DUPLICADOS Y VERSIONES
# ==========================================
def analyze_duplicates(docs, doc_texts):
    rows = []

    # Idénticos por archivo o por texto
    for col, label in [("hash_archivo", "archivo idéntico"),
                       ("hash_texto", "texto idéntico")]:
        for _, grp in docs.groupby(col):
            if len(grp) > 1:
                rows.append({"tipo": label,
                             "documentos": " | ".join(grp["documento"]),
                             "similitud": 1.0})

    # Casi-duplicados (posibles versiones) por similitud de contenido
    sh = {name: shingles(txt) for name, txt in doc_texts.items()}
    for a, b in itertools.combinations(sh, 2):
        inter = len(sh[a] & sh[b])
        union = len(sh[a] | sh[b])
        sim = inter / union if union else 0
        if SIMILARITY_THRESHOLD <= sim < 1.0:
            rows.append({"tipo": "casi duplicado (posible versión)",
                         "documentos": f"{a} | {b}",
                         "similitud": round(sim, 3)})

    # Mismo nombre base con distinto archivo (versiones históricas por nombre)
    for base, grp in docs.groupby("nombre_base"):
        if len(grp) > 1 and base:
            rows.append({"tipo": "mismo nombre base (revisar versiones)",
                         "documentos": " | ".join(grp["documento"]),
                         "similitud": None})

    return pd.DataFrame(rows, columns=["tipo", "documentos", "similitud"])


# ==========================================
# 3. ANÁLISIS DE FRAGMENTOS (desde ChromaDB)
# ==========================================
def analyze_chunks():
    col = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(COLLECTION)
    data = col.get(include=["documents", "metadatas"])

    rows = []
    for text, meta in zip(data["documents"], data["metadatas"]):
        rows.append({
            "documento": Path(str(meta.get("source", "desconocido"))).name,
            "pagina": meta.get("page"),
            "caracteres": len(text),
            "palabras": len(text.split()),
            "tokens_aprox": round(len(text) / 4),
            "texto_hash": hashlib.md5(text.encode()).hexdigest(),
        })
    return pd.DataFrame(rows)


# ==========================================
# 4. GRÁFICAS
# ==========================================
def save_charts(docs, pages, chunks):
    def finish(name):
        plt.tight_layout()
        plt.savefig(OUT / name, dpi=150)
        plt.close()

    docs["categoria"].value_counts().plot.bar(color="#2E5C8A")
    plt.title("Documentos por categoría"); plt.ylabel("Documentos")
    finish("01_documentos_por_categoria.png")

    pages.groupby(["categoria", "tipo_pagina"]).size().unstack(fill_value=0) \
        .plot.bar(stacked=True)
    plt.title("Tipo de página por categoría"); plt.ylabel("Páginas")
    finish("02_tipo_de_pagina.png")

    pages[pages["caracteres"] > 0]["caracteres"].plot.hist(bins=40, color="#2E5C8A")
    plt.title("Distribución de caracteres por página"); plt.xlabel("Caracteres")
    finish("03_caracteres_por_pagina.png")

    docs.set_index("documento")["paginas"].sort_values().plot.barh(color="#2E5C8A")
    plt.title("Páginas por documento"); plt.xlabel("Páginas")
    finish("04_paginas_por_documento.png")

    if not chunks.empty:
        chunks["caracteres"].plot.hist(bins=40, color="#8A5C2E")
        plt.title("Distribución del tamaño de fragmentos"); plt.xlabel("Caracteres")
        finish("05_tamano_fragmentos.png")

        chunks["documento"].value_counts().sort_values().plot.barh(color="#8A5C2E")
        plt.title("Fragmentos por documento"); plt.xlabel("Fragmentos")
        finish("06_fragmentos_por_documento.png")


# ==========================================
# 5. MAIN
# ==========================================
def main():
    print("Analizando PDFs (puede tardar por la detección de tablas)...")
    docs, pages, doc_texts = analyze_pdfs()
    dups = analyze_duplicates(docs, doc_texts)

    try:
        chunks = analyze_chunks()
    except Exception as e:
        print(f"⚠ No se pudo leer ChromaDB: {e}")
        chunks = pd.DataFrame()

    # ---- Tablas por documento ----
    per_doc = pages.groupby("documento").agg(
        paginas=("pagina", "count"),
        paginas_con_texto=("tipo_pagina", lambda s: (s == "con texto").sum()),
        paginas_escaneadas=("tipo_pagina", lambda s: s.str.startswith("escaneada").sum()),
        paginas_vacias=("tipo_pagina", lambda s: (s == "vacía").sum()),
        caracteres_totales=("caracteres", "sum"),
        caracteres_por_pagina_media=("caracteres", "mean"),
        tablas=("tablas", "sum"),
        articulos=("articulos", "sum"),
        encabezados=("encabezados", "sum"),
        elementos_lista=("elementos_lista", "sum"),
    ).round(1).reset_index()
    per_doc = per_doc.merge(docs[["documento", "categoria"]], on="documento")

    if not chunks.empty:
        n_chunks = chunks.groupby("documento").size().rename("fragmentos").reset_index()
        per_doc = per_doc.merge(n_chunks, on="documento", how="left")
        per_doc["fragmentos"] = per_doc["fragmentos"].fillna(0).astype(int)

    # ---- Guardar CSVs ----
    per_doc.to_csv(OUT / "resumen_por_documento.csv", index=False, encoding="utf-8-sig")
    pages.to_csv(OUT / "detalle_paginas.csv", index=False, encoding="utf-8-sig")
    dups.to_csv(OUT / "duplicados_y_versiones.csv", index=False, encoding="utf-8-sig")
    if not chunks.empty:
        chunks.drop(columns="texto_hash").to_csv(
            OUT / "detalle_fragmentos.csv", index=False, encoding="utf-8-sig")

    save_charts(docs, pages, chunks)

    # ---- Resumen general ----
    pct = lambda n, t: round(100 * n / t, 1) if t else 0
    total_pages = len(pages)
    summary = {
        "total_documentos": len(docs),
        "total_paginas": total_pages,
        "documentos_por_categoria": docs["categoria"].value_counts().to_dict(),
        "paginas_con_texto": int((pages["tipo_pagina"] == "con texto").sum()),
        "paginas_escaneadas": int(pages["tipo_pagina"].str.startswith("escaneada").sum()),
        "paginas_vacias": int((pages["tipo_pagina"] == "vacía").sum()),
        "caracteres_totales": int(docs["caracteres"].sum()),
        "caracteres_por_pagina": pages["caracteres"].describe().round(1).to_dict(),
        "paginas_por_documento": docs["paginas"].describe().round(1).to_dict(),
        "paginas_con_tablas": int((pages["tablas"] > 0).sum()),
        "total_articulos_detectados": int(pages["articulos"].sum()),
        "total_encabezados_detectados": int(pages["encabezados"].sum()),
        "total_elementos_lista": int(pages["elementos_lista"].sum()),
        "documentos_sin_articulos": per_doc.loc[per_doc["articulos"] == 0, "documento"].tolist(),
        "grupos_duplicados_o_versiones": len(dups),
    }
    if not chunks.empty:
        summary["total_fragmentos"] = len(chunks)
        summary["tamano_fragmento_caracteres"] = chunks["caracteres"].describe().round(1).to_dict()
        summary["tamano_fragmento_tokens_aprox"] = chunks["tokens_aprox"].describe().round(1).to_dict()
        summary["fragmentos_por_documento"] = chunks.groupby("documento").size() \
            .describe().round(1).to_dict()
        summary["fragmentos_duplicados_exactos"] = int(chunks["texto_hash"].duplicated().sum())
        summary["fragmentos_menores_a_200_caracteres"] = int((chunks["caracteres"] < 200).sum())

    (OUT / "resumen_general.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    # ---- Impresión ----
    print("\n" + "=" * 60)
    print("RESUMEN DEL CORPUS")
    print("=" * 60)
    print(f"Documentos: {summary['total_documentos']}  |  Páginas: {total_pages}")
    print(f"Con texto: {summary['paginas_con_texto']} "
          f"({pct(summary['paginas_con_texto'], total_pages)}%)  |  "
          f"Escaneadas: {summary['paginas_escaneadas']}  |  "
          f"Vacías: {summary['paginas_vacias']}")
    print(f"Artículos: {summary['total_articulos_detectados']}  |  "
          f"Encabezados: {summary['total_encabezados_detectados']}  |  "
          f"Páginas con tablas: {summary['paginas_con_tablas']}  |  "
          f"Elementos de lista: {summary['total_elementos_lista']}")
    if not chunks.empty:
        print(f"Fragmentos: {summary['total_fragmentos']}  |  "
              f"Tamaño medio: {summary['tamano_fragmento_caracteres']['mean']} caracteres")
    print("\nPor categoría:")
    print(docs["categoria"].value_counts().to_string())
    print("\nDuplicados / versiones:")
    print(dups.to_string(index=False) if not dups.empty else "Ninguno detectado")
    if summary["documentos_sin_articulos"]:
        print("\n⚠ Sin artículos detectados (normal en convocatorias):")
        for d in summary["documentos_sin_articulos"]:
            print(f"  - {d}")
    print(f"\nArchivos guardados en: {OUT.resolve()}")


if __name__ == "__main__":
    main()