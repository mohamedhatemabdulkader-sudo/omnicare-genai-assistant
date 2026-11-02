import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastembed import TextEmbedding
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver

from app.agent import build_assistant_graph
from app.api import router
from app.claims import ClaimsRepository
from app.config import Settings, get_settings
from app.guard import PromptGuard
from app.rag import PolicyStore, create_qdrant_client
from app.service import AssistantService
from app.tools import build_tools

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_llm(settings: Settings) -> ChatGoogleGenerativeAI:
    api_key = settings.google_api_key.get_secret_value() if settings.google_api_key else ""
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set. Add it to backend/.env (see .env.example).")
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=api_key,
        temperature=0,
        timeout=settings.llm_timeout_seconds,
        max_retries=5,
    )


def build_assistant(settings: Settings) -> AssistantService:
    llm = create_llm(settings)
    embedder = TextEmbedding(settings.embedding_model, cache_dir=settings.embedding_cache_dir)
    store = PolicyStore(create_qdrant_client(settings), embedder, settings.qdrant_collection)
    store.ingest(settings.policy_path)
    tools = build_tools(store, ClaimsRepository(settings.claims_path), settings.rag_top_k)
    guard = PromptGuard(llm if settings.guard_llm_enabled else None)
    return AssistantService(build_assistant_graph(llm, tools, guard, InMemorySaver()))


def create_app(assistant: AssistantService | None = None) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.assistant = assistant or build_assistant(settings)
        yield

    app = FastAPI(title="OmniCare Assistant API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)
    return app


app = create_app()
