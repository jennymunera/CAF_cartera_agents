
# Prompt de Arquitectura (Alto Nivel) para crear un RAG con Azure Document Intelligence + ChromaDB + CrewAI

> **Objetivo**: Este prompt será consumido por un LLM para **diseñar e implementar** un sistema **RAG** productivo, con extracción documental usando **Azure AI Document Intelligence Studio**, recuperación **híbrida** con **embeddings + búsqueda léxica**, **ChromaDB** como base vectorial, **re‑ranking** y **verificación de groundedness**, orquestado por **CrewAI** en un pipeline de agentes.

---

## 1) Rol del sistema (instrucciones no negociables)

Eres un arquitecto/implementador IA. Debes **entregar código y artefactos ejecutables** (Python) para un RAG robusto, modular y medible. Aplica principios de seguridad, observabilidad y reproducibilidad (Docker).

---

## 2) Ingesta y extracción (Azure AI Document Intelligence)

- Usa **Azure AI Document Intelligence Studio** para procesar **PDFs, imágenes, formularios, facturas, contratos y documentos escaneados**.

- Limpieza y enriquecimiento:
  - Normaliza a **UTF‑8**, corrige OCR básico (ligaduras, artefactos).
  - **Detección de idioma** por página/bloque.
  - **Segmentación semántica por layout**: agrupa párrafos bajo sus encabezados.


---

## 3) Indexación (Embeddings + ChromaDB)

- **Chunking**: tamaño objetivo **1.000 tokens** (rango 800–1.200) con **overlap 100**; une párrafos cortos y respeta límites de sección.
- **Embeddings**: por defecto **sentence-transformers/all-MiniLM-L6-v2** (multilingüe, embeddings densos). Exponer flags:
  - `normalize=True`
  - Soporte para múltiples modelos de embeddings
- **Vector DB**: **ChromaDB** con índice **HNSW** (m=64, ef_search=128). Guarda **metadata rica** por chunk: `doc_id, page, section_path, lang, hash, source_type, table_presence, kv_presence, ingestion_ts`.
- Implementa **filtros por metadata** en consultas (e.g., por `doc_id`, rango de fechas, `lang`, presencia de tablas).

**Entregable**: módulo `indexer.py` con:
- `build_index(chunks: List[DocChunk]) -> None`
- `upsert_chunks(chunks: List[DocChunk]) -> None`

---

## 4) Recuperación híbrida y fusión

- **Consulta híbrida**:
  - **Denso**: embeddings de consulta.
  - **Disperso/léxico**: pesos términos (del propio **bge-m3**) o BM25 externo.
- **Fusión de resultados**:
  - **RRF (Reciprocal Rank Fusion)** por defecto.
  - Alternativa: suma ponderada `score = 0.6*dense + 0.4*sparse` (parametrizable).
- **Pre‑filtros por metadata** (ej., colección, tipo de documento, fecha, idioma) antes de KNN.
- Devuelve top‑N candidatos (N=100) con trazabilidad (`doc_id:page:block_id` y scores).

**Entregable**: `retrieve(query: str, k_dense=50, k_sparse=50, filters: dict=None) -> List[Candidate]`

---

## 5) Re‑ranking (Cross‑Encoder)

- Aplica **cross-encoder** para re-ranking sobre el **top‑100** y devuelve **top‑k final** (k=5–8).
- Interfaz: `rerank(query, candidates: List[Candidate], top_k=8) -> List[Candidate]`.

