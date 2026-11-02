export type ToolCall = {
  name: string;
  args: Record<string, unknown>;
  output?: string | null;
  status?: "success" | "error" | null;
};

export type ChatResult = {
  response: string;
  sources: string[];
  tool_calls: ToolCall[];
};

export type StreamHandlers = {
  onToken: (text: string) => void;
  onToolCall: (call: ToolCall) => void;
  onDone: (result: ChatResult) => void;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const EVENT_SEPARATOR = "\n\n";

export async function streamChat(
  userId: string,
  message: string,
  handlers: StreamHandlers,
): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, message }),
  });
  if (!response.ok || !response.body) {
    throw new Error(await describeHttpError(response));
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let boundary = buffer.indexOf(EVENT_SEPARATOR);
    while (boundary !== -1) {
      dispatchEvent(buffer.slice(0, boundary), handlers);
      buffer = buffer.slice(boundary + EVENT_SEPARATOR.length);
      boundary = buffer.indexOf(EVENT_SEPARATOR);
    }
  }
}

function dispatchEvent(block: string, handlers: StreamHandlers): void {
  let event = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice("event: ".length);
    else if (line.startsWith("data: ")) data += line.slice("data: ".length);
  }
  const payload = JSON.parse(data);

  if (event === "token") handlers.onToken(payload.text);
  else if (event === "tool_call") handlers.onToolCall(payload);
  else if (event === "done") handlers.onDone(payload);
  else if (event === "error") throw new Error(payload.detail);
}

async function describeHttpError(response: Response): Promise<string> {
  if (response.status === 422) {
    return "That message couldn't be sent. Messages must be 1–2000 characters.";
  }
  const body = await response.json().catch(() => null);
  return body?.detail ?? `The assistant is unavailable (HTTP ${response.status}).`;
}
