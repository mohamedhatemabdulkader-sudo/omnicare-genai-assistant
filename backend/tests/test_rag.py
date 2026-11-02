import pytest

from app.rag import split_policy_by_section
from tests.conftest import PERSONAL_PROPERTY, POLICY_PATH, WATER_DAMAGE


def test_policy_is_split_into_one_chunk_per_section():
    chunks = split_policy_by_section(POLICY_PATH.read_text(encoding="utf-8"), "sample_policy.md")

    assert [c.citation for c in chunks] == [WATER_DAMAGE, PERSONAL_PROPERTY]
    assert "$25,000" in chunks[0].text
    assert "$10,000" in chunks[1].text


@pytest.mark.parametrize(
    ("question", "expected_citation"),
    [
        ("Is damage from a burst pipe covered?", WATER_DAMAGE),
        ("What is the deductible for flood or leak damage?", WATER_DAMAGE),
        ("Do I need a receipt for an expensive necklace?", PERSONAL_PROPERTY),
        ("How much is covered for my laptop and sofa?", PERSONAL_PROPERTY),
    ],
)
def test_search_ranks_the_relevant_section_first(policy_store, question, expected_citation):
    results = policy_store.search(question, top_k=2)

    assert results[0].chunk.citation == expected_citation


def test_ingest_is_idempotent(policy_store):
    policy_store.ingest(POLICY_PATH)

    assert len(policy_store.search("coverage", top_k=10)) == 2


def test_search_policy_tool_returns_cited_content_and_sources(tools):
    message = tools["search_policy"].invoke(
        {"type": "tool_call", "name": "search_policy", "id": "1", "args": {"query": "pipe burst"}}
    )

    assert message.artifact[0] == WATER_DAMAGE
    assert f"[{WATER_DAMAGE}]" in message.content
