import json
import re

import pytest
from pydantic import ValidationError

VALID_CLAIM = {
    "policy_number": "POL-1092",
    "claim_type": "Water Damage",
    "amount": 1800.50,
    "description": "Pipe burst under the kitchen sink overnight.",
}


def read_claims(path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_get_claim_status_returns_existing_claim(tools):
    result = json.loads(tools["get_claim_status"].invoke({"claim_id": "CLM-8821"}))

    assert result["status"] == "Approved"
    assert result["policy_number"] == "POL-1092"


def test_get_claim_status_reports_unknown_claim(tools):
    result = tools["get_claim_status"].invoke({"claim_id": "CLM-0000"})

    assert result.startswith("No claim found with ID CLM-0000")


@pytest.mark.parametrize("claim_id", ["8821", "clm8821", "CLM-12", "CLM-8821; DROP"])
def test_get_claim_status_rejects_malformed_ids(tools, claim_id):
    with pytest.raises(ValidationError):
        tools["get_claim_status"].invoke({"claim_id": claim_id})


def test_submit_claim_appends_record_and_returns_confirmation(tools, claims_path):
    result = tools["submit_claim"].invoke(VALID_CLAIM)

    claim_id = re.search(r"Confirmation ID: (CLM-\d{4})", result).group(1)
    claims = read_claims(claims_path)
    assert len(claims) == 3
    assert claims[-1] == {
        "claim_id": claim_id,
        "policy_number": "POL-1092",
        "claim_type": "Water Damage",
        "status": "Submitted",
        "amount": 1800.5,
        "description": "Pipe burst under the kitchen sink overnight.",
    }
    assert json.loads(tools["get_claim_status"].invoke({"claim_id": claim_id}))["status"] == (
        "Submitted"
    )


@pytest.mark.parametrize(
    "override",
    [
        {"policy_number": "1092"},
        {"claim_type": "Car Accident"},
        {"amount": 0},
        {"amount": -50},
        {"amount": 12.345},
        {"amount": "lots"},
        {"amount": 5_000_000},
        {"description": "short"},
    ],
)
def test_submit_claim_rejects_invalid_input_without_writing(tools, claims_path, override):
    with pytest.raises(ValidationError):
        tools["submit_claim"].invoke({**VALID_CLAIM, **override})

    assert len(read_claims(claims_path)) == 2


def test_submitted_claim_ids_are_unique(tools):
    results = [tools["submit_claim"].invoke(VALID_CLAIM) for _ in range(20)]

    ids = {re.search(r"CLM-\d{4}", r).group(0) for r in results}
    assert len(ids) == 20
