import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastembed import TextEmbedding
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr
from qdrant_client import QdrantClient

from app.claims import ClaimsRepository
from app.config import DATA_DIR
from app.rag import PolicyStore
from app.tools import build_tools

POLICY_PATH = DATA_DIR / "sample_policy.md"
WATER_DAMAGE = "sample_policy.md § Section 1: Home Water Damage Coverage"
PERSONAL_PROPERTY = "sample_policy.md § Section 2: Personal Property Protection"


class ScriptedChatModel(BaseChatModel):
    """Returns pre-scripted AI messages in order; fails loudly if called more than scripted."""

    responses: list[AIMessage]
    _cursor: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    @property
    def call_count(self) -> int:
        return self._cursor

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        if self._cursor >= len(self.responses):
            raise AssertionError("ScriptedChatModel called more times than scripted")
        message = self.responses[self._cursor]
        self._cursor += 1
        return ChatResult(generations=[ChatGeneration(message=message)])


def tool_call(name: str, args: dict, call_id: str = "call_1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


@pytest.fixture(scope="session")
def embedder() -> TextEmbedding:
    return TextEmbedding("BAAI/bge-small-en-v1.5")


@pytest.fixture(scope="session")
def policy_store(embedder: TextEmbedding) -> PolicyStore:
    store = PolicyStore(QdrantClient(location=":memory:"), embedder, "test_policies")
    store.ingest(POLICY_PATH)
    return store


@pytest.fixture
def claims_path(tmp_path: Path) -> Path:
    path = tmp_path / "mock_claims.json"
    shutil.copy(DATA_DIR / "mock_claims.json", path)
    return path


@pytest.fixture
def claims_repo(claims_path: Path) -> ClaimsRepository:
    return ClaimsRepository(claims_path)


@pytest.fixture
def tools(policy_store: PolicyStore, claims_repo: ClaimsRepository) -> dict:
    return {t.name: t for t in build_tools(policy_store, claims_repo, top_k=2)}


@pytest.fixture
def no_llm_calls() -> Iterator[ScriptedChatModel]:
    yield ScriptedChatModel(responses=[])
