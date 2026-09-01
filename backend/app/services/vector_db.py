import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings


def get_chroma_client():
    """
    Returns an initialized ChromaDB client depending on configuration:
    - If CHROMA_USE_SERVER is True: connects to HttpClient (e.g. running via Docker)
    - Otherwise: initializes PersistentClient at CHROMA_PERSIST_DIR
    """
    if settings.CHROMA_USE_SERVER:
        return chromadb.HttpClient(
            host=settings.CHROMA_HOST,
            port=settings.CHROMA_PORT,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
    else:
        return chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False)
        )


def get_or_create_collection(name: str = "role_knowledge_base"):
    """
    Retrieves or creates a ChromaDB collection for role-specific knowledge embeddings.
    """
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"}
    )
