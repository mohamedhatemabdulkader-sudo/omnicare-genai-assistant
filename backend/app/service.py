from collections.abc import AsyncIterator, Iterable, Sequence
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from app.schemas import ChatResponse, ToolCallRecord

RECURSION_LIMIT = 12
POLICY_TOOL = "search_policy"


class AssistantService:
    def __init__(self, graph: CompiledStateGraph) -> None:
        self._graph = graph

    async def chat(self, user_id: str, message: str) -> ChatResponse:
        config = self._config(user_id)
        prior_count = await self._message_count(config)
        await self._graph.ainvoke({"messages": [HumanMessage(message)]}, config)
        return await self._turn_result(config, prior_count)

    async def stream_chat(self, user_id: str, message: str) -> AsyncIterator[tuple[str, Any]]:
        """Yields ("token", text), ("tool_call", record) and finally ("done", ChatResponse)."""
        config = self._config(user_id)
        prior_count = await self._message_count(config)
        stream = self._graph.astream(
            {"messages": [HumanMessage(message)]}, config, stream_mode=["messages", "updates"]
        )
        async for mode, payload in stream:
            if mode == "messages":
                chunk, metadata = payload
                if metadata.get("langgraph_node") == "agent" and isinstance(chunk, AIMessageChunk):
                    if chunk.text:
                        yield "token", chunk.text
            elif "agent" in payload:
                for call in payload["agent"]["messages"][-1].tool_calls:
                    yield "tool_call", ToolCallRecord(name=call["name"], args=call["args"])
        yield "done", await self._turn_result(config, prior_count)

    @staticmethod
    def _config(user_id: str) -> RunnableConfig:
        return {"configurable": {"thread_id": user_id}, "recursion_limit": RECURSION_LIMIT}

    async def _message_count(self, config: RunnableConfig) -> int:
        snapshot = await self._graph.aget_state(config)
        return len(snapshot.values.get("messages", []))

    async def _turn_result(self, config: RunnableConfig, prior_count: int) -> ChatResponse:
        snapshot = await self._graph.aget_state(config)
        return summarize_turn(snapshot.values["messages"][prior_count:])


def summarize_turn(messages: Sequence[BaseMessage]) -> ChatResponse:
    ai_messages = [m for m in messages if isinstance(m, AIMessage)]
    tool_results = {m.tool_call_id: m for m in messages if isinstance(m, ToolMessage)}
    response = ai_messages[-1].text if ai_messages else ""
    tool_calls = [
        _tool_call_record(call, tool_results.get(call["id"]))
        for message in ai_messages
        for call in message.tool_calls
    ]
    return ChatResponse(
        response=response,
        sources=_cited_sources(response, tool_results.values()),
        tool_calls=tool_calls,
    )


def _tool_call_record(call: dict, result: ToolMessage | None) -> ToolCallRecord:
    return ToolCallRecord(
        name=call["name"],
        args=call["args"],
        output=result.text if result else None,
        status=result.status if result else None,
    )


def _cited_sources(response: str, tool_results: Iterable[ToolMessage]) -> list[str]:
    """Retrieved sections the answer actually references; all retrieved ones if none match."""
    retrieved = list(
        dict.fromkeys(
            citation
            for result in tool_results
            if result.name == POLICY_TOOL and result.artifact
            for citation in result.artifact
        )
    )
    cited = [c for c in retrieved if c.split(" § ", 1)[-1].lower() in response.lower()]
    return cited or retrieved
