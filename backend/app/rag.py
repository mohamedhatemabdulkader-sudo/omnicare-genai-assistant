import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import Settings

logger = logging.getLogger(__name__)

SECTION_HEADING = re.compile(r"^##\s+(.+)$", re.MULTILINE)
CHUNK_ID_NAMESPACE = uuid.UUID("6f1c2a52-5d0e-4c4e-9a3e-0d6b7f1d2c11")


@dataclass(frozen=True)
class PolicyChunk:
    source: str
    section: str
    text: str

    @property
    def citation(self) -> str:
        return f"{self.source} § {self.section}"


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: PolicyChunk
    score: float


def split_policy_by_section(markdown: str, source: str) -> list[PolicyChunk]:
    """One chunk per `##` section, so every chunk maps to exactly one citable section."""
    headings = list(SECTION_HEADING.finditer(markdown))
    chunks = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(markdown)
        body = markdown[heading.end():end].strip()
        if body:
            section = heading.group(1).strip()
            chunks.append(PolicyChunk(source=source, section=section, text=body))
    return chunks


def create_qdrant_client(settings: Settings) -> QdrantClient:
    if settings.uses_qdrant_cloud:
        api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        logger.info("Using Qdrant Cloud at %s", settings.qdrant_url)
        return QdrantClient(url=settings.qdrant_url, api_key=api_key, timeout=10)
    logger.info("Using local Qdrant at %s", settings.qdrant_local_path)
    return QdrantClient(path=settings.qdrant_local_path)


class PolicyStore:
    def __init__(self, client: QdrantClient, embedder: TextEmbedding, collection: str) -> None:
        self._client = client
        self._embedder = embedder
        self._collection = collection

    def ingest(self, policy_path: Path) -> int:
        chunks = split_policy_by_section(policy_path.read_text(encoding="utf-8"), policy_path.name)
        if not chunks:
            raise ValueError(f"No '## ' sections found in {policy_path}")
        vectors = list(self._embedder.embed([f"{c.section}\n{c.text}" for c in chunks]))
        self._ensure_collection(len(vectors[0]))
        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(
                    id=str(uuid.uuid5(CHUNK_ID_NAMESPACE, chunk.citation)),
                    vector=vector.tolist(),
                    payload={"source": chunk.source, "section": chunk.section, "text": chunk.text},
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ],
        )
        logger.info("Ingested %d policy sections into '%s'", len(chunks), self._collection)
        return len(chunks)

    def search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        query_vector = next(iter(self._embedder.query_embed(query)))
        result = self._client.query_points(
            collection_name=self._collection, query=query_vector.tolist(), limit=top_k
        )
        return [
            RetrievedChunk(
                chunk=PolicyChunk(
                    source=point.payload["source"],
                    section=point.payload["section"],
                    text=point.payload["text"],
                ),
                score=point.score,
            )
            for point in result.points
        ]

    def _ensure_collection(self, vector_size: int) -> None:
        if self._client.collection_exists(self._collection):
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
