from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.f1_models import RaceDocument
import uuid

# Loaded once per process — loading this repeatedly is slow (~1-2s each time).
_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print("  🧠 Loading embedding model (all-MiniLM-L6-v2)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> list[float]:
    """Embed a single string into a 384-dim vector matching RaceDocument.embedding."""
    model = get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-embed multiple strings at once — faster than calling embed_text in a loop."""
    model = get_embedding_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return vectors.tolist()


async def store_documents(
    db: AsyncSession,
    session_key: int,
    documents: list[dict],
    replace_existing: bool = True,
) -> int:
    """
    Embeds and stores a list of {"doc_type": ..., "content": ...} dicts
    as RaceDocument rows for the given session_key.

    If replace_existing=True, deletes any prior documents for this session_key
    first (safe to re-run after re-ingestion).
    """
    if replace_existing:
        await db.execute(
            delete(RaceDocument).where(RaceDocument.session_key == session_key)
        )
        await db.flush()

    if not documents:
        return 0

    texts = [doc["content"] for doc in documents]
    vectors = embed_texts(texts)

    for doc, vector in zip(documents, vectors):
        race_doc = RaceDocument(
            id=uuid.uuid4(),
            session_key=session_key,
            doc_type=doc["doc_type"],
            content=doc["content"],
            embedding=vector,
            metadata_=None,
        )
        db.add(race_doc)

    await db.flush()
    return len(documents)


async def search_similar_documents(
    db: AsyncSession,
    query: str,
    session_key: int | None = None,
    limit: int = 5,
) -> list[RaceDocument]:
    """
    Embeds the query and finds the most similar RaceDocuments via pgvector
    cosine distance. Optionally restricts to a single session_key.
    """
    query_vector = embed_text(query)

    stmt = select(RaceDocument).order_by(
        RaceDocument.embedding.cosine_distance(query_vector)
    ).limit(limit)

    if session_key is not None:
        stmt = stmt.where(RaceDocument.session_key == session_key)

    result = await db.execute(stmt)
    return result.scalars().all()