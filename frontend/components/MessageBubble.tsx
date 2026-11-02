import type { ToolCall } from "@/lib/chat";

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: string[];
  toolCalls: ToolCall[];
  pending: boolean;
  error?: string;
};

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <article className={`bubble ${isUser ? "bubble-user" : "bubble-assistant"}`}>
      {message.toolCalls.length > 0 && <ToolCallList calls={message.toolCalls} />}
      {message.content ? (
        <p className="bubble-text">{message.content}</p>
      ) : (
        message.pending && <p className="typing">Thinking…</p>
      )}
      {message.error && <p className="bubble-error">{message.error}</p>}
      {message.sources.length > 0 && <SourceList sources={message.sources} />}
    </article>
  );
}

function SourceList({ sources }: { sources: string[] }) {
  return (
    <div className="sources">
      <span className="sources-label">Sources</span>
      <ul>
        {sources.map((source) => (
          <li key={source} className="source-chip">
            {source}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ToolCallList({ calls }: { calls: ToolCall[] }) {
  return (
    <details className="tools">
      <summary>
        Used {calls.length} tool{calls.length > 1 ? "s" : ""}:{" "}
        {calls.map((call) => call.name).join(", ")}
      </summary>
      {calls.map((call, index) => (
        <div key={`${call.name}-${index}`} className="tool-call">
          <div className="tool-name">
            {call.name}
            {call.status && <span className={`tool-status ${call.status}`}>{call.status}</span>}
          </div>
          <pre>{JSON.stringify(call.args, null, 2)}</pre>
          {call.output && <pre className="tool-output">{call.output}</pre>}
        </div>
      ))}
    </details>
  );
}
