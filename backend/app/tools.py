from decimal import Decimal

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from app.claims import CLAIM_ID_PATTERN, ClaimsRepository, ClaimSubmission
from app.rag import PolicyStore


class PolicySearchInput(BaseModel):
    query: str = Field(min_length=3, max_length=500, description="The coverage question to look up")


class ClaimStatusInput(BaseModel):
    claim_id: str = Field(pattern=CLAIM_ID_PATTERN, description="Claim ID, e.g. CLM-8821")


def build_tools(store: PolicyStore, claims: ClaimsRepository, top_k: int) -> list[BaseTool]:
    @tool(args_schema=PolicySearchInput, response_format="content_and_artifact")
    def search_policy(query: str) -> tuple[str, list[str]]:
        """Search the OmniCare policy document for coverage rules, limits, deductibles and
        exclusions. Use this for any question about what the policy covers."""
        results = store.search(query, top_k)
        if not results:
            return "No relevant policy sections were found.", []
        content = "\n\n".join(f"[{r.chunk.citation}]\n{r.chunk.text}" for r in results)
        return content, [r.chunk.citation for r in results]

    @tool(args_schema=ClaimStatusInput)
    def get_claim_status(claim_id: str) -> str:
        """Look up the current status of an existing insurance claim by its claim ID."""
        claim = claims.get(claim_id)
        if claim is None:
            return f"No claim found with ID {claim_id}. Ask the customer to double-check it."
        return claim.model_dump_json(exclude_none=True)

    @tool(args_schema=ClaimSubmission)
    def submit_claim(
        policy_number: str, claim_type: str, amount: Decimal, description: str
    ) -> str:
        """File a new insurance claim. Only call this once the customer has provided the
        policy number, claim type, amount and a description of what happened."""
        submission = ClaimSubmission(
            policy_number=policy_number,
            claim_type=claim_type,
            amount=amount,
            description=description,
        )
        claim = claims.add(submission)
        return (
            f"Claim submitted. Confirmation ID: {claim.claim_id}. "
            f"Status: {claim.status}. Amount: ${claim.amount:,.2f}."
        )

    return [search_policy, get_claim_status, submit_claim]
