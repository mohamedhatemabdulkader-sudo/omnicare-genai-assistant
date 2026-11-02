import json
import os
import secrets
import threading
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, WithJsonSchema

ClaimType = Literal["Water Damage", "Personal Property"]

CLAIM_ID_PATTERN = r"^CLM-\d{4,8}$"
POLICY_NUMBER_PATTERN = r"^POL-\d{4,8}$"
NEW_CLAIM_STATUS = "Submitted"
MAX_ID_ATTEMPTS = 100


class ClaimSubmission(BaseModel):
    """Input for filing a new insurance claim."""

    model_config = {"extra": "forbid"}

    policy_number: str = Field(
        pattern=POLICY_NUMBER_PATTERN, description="Policy number, e.g. POL-1092"
    )
    claim_type: ClaimType = Field(description="Type of loss being claimed")
    amount: Annotated[
        Decimal,
        WithJsonSchema({"type": "number", "description": "Claimed amount in USD, e.g. 1250.00"}),
    ] = Field(gt=0, le=1_000_000, decimal_places=2)
    description: str = Field(
        min_length=10, max_length=1000, description="What happened, in the customer's words"
    )


class Claim(BaseModel):
    claim_id: str
    policy_number: str
    claim_type: str
    status: str
    amount: Decimal
    description: str | None = None


class ClaimsRepository:
    """JSON-file claim store. Writes are serialized and atomic (temp file + replace)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def get(self, claim_id: str) -> Claim | None:
        normalized = claim_id.strip().upper()
        return next((c for c in self._load() if c.claim_id == normalized), None)

    def add(self, submission: ClaimSubmission) -> Claim:
        with self._lock:
            claims = self._load()
            claim = Claim(
                claim_id=self._new_claim_id({c.claim_id for c in claims}),
                status=NEW_CLAIM_STATUS,
                **submission.model_dump(),
            )
            self._save([*claims, claim])
            return claim

    def _load(self) -> list[Claim]:
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return [Claim.model_validate(item) for item in raw]

    def _save(self, claims: list[Claim]) -> None:
        payload = [c.model_dump(mode="json", exclude_none=True) for c in claims]
        for item in payload:
            item["amount"] = float(item["amount"])
        tmp_path = self._path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_path, self._path)

    @staticmethod
    def _new_claim_id(existing: set[str]) -> str:
        for _ in range(MAX_ID_ATTEMPTS):
            candidate = f"CLM-{secrets.randbelow(9000) + 1000}"
            if candidate not in existing:
                return candidate
        raise RuntimeError("Could not allocate a unique claim ID; claim store is nearly full")
