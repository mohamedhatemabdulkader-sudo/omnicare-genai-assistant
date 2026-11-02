"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { Message, MessageBubble } from "@/components/MessageBubble";
import { streamChat } from "@/lib/chat";

const USER_ID_KEY = "omnicare_user_id";
const SUGGESTIONS = [
  "Is water damage from a burst pipe covered?",
  "Do I need a receipt for a $3,000 necklace?",
  "What's the status of claim CLM-9014?",
  "I want to file a water damage claim for $1,800 on policy POL-1092. A pipe burst under my sink.",
];

function newUserId(): string {
  return `usr_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;
}

function newMessage(role: Message["role"], content = ""): Message {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    sources: [],
    toolCalls: [],
    pending: role === "assistant",
  };
}

export default function ChatPage() {
  const [userId, setUserId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const stored = localStorage.getItem(USER_ID_KEY);
    const id = stored ?? newUserId();
    localStorage.setItem(USER_ID_KEY, id);
    setUserId(id);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function updateMessage(id: string, update: (message: Message) => Message) {
    setMessages((current) => current.map((m) => (m.id === id ? update(m) : m)));
  }

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || busy || !userId) return;

    const reply = newMessage("assistant");
    setMessages((current) => [...current, newMessage("user", trimmed), reply]);
    setInput("");
    setBusy(true);
    try {
      await streamChat(userId, trimmed, {
        onToken: (token) => updateMessage(reply.id, (m) => ({ ...m, content: m.content + token })),
        onToolCall: (call) =>
          updateMessage(reply.id, (m) => ({ ...m, toolCalls: [...m.toolCalls, call] })),
        onDone: (result) =>
          updateMessage(reply.id, (m) => ({
            ...m,
            content: result.response,
            sources: result.sources,
            toolCalls: result.tool_calls,
            pending: false,
          })),
      });
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Something went wrong.";
      updateMessage(reply.id, (m) => ({ ...m, pending: false, error: detail }));
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }

  function startNewConversation() {
    const id = newUserId();
    localStorage.setItem(USER_ID_KEY, id);
    setUserId(id);
    setMessages([]);
  }

  return (
    <main className="shell">
      <header className="header">
        <div>
          <h1>OmniCare Assistant</h1>
          <p className="subtitle">Policy coverage, claim status and new claims</p>
        </div>
        <div className="session">
          <code>{userId}</code>
          <button type="button" className="ghost" onClick={startNewConversation} disabled={busy}>
            New conversation
          </button>
        </div>
      </header>

      <section className="thread" aria-live="polite">
        {messages.length === 0 && (
          <div className="empty">
            <p>Try one of these:</p>
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="suggestion"
                onClick={() => void send(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        <div ref={bottomRef} />
      </section>

      <form className="composer" onSubmit={onSubmit}>
        <label htmlFor="message" className="visually-hidden">
          Message
        </label>
        <input
          id="message"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask about your coverage or a claim…"
          maxLength={2000}
          autoComplete="off"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          {busy ? "Sending…" : "Send"}
        </button>
      </form>
    </main>
  );
}
