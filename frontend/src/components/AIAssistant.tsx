import { useRef, useState, type FormEvent } from "react";
import { aiApi, ApiError } from "../api/client";
import type { AIChatResponse } from "../types";

const MAX_MESSAGE_LENGTH = 1000;
const examples = [
  "What can you help me with?",
  "List the teachers.",
  "Show me the current published schedule.",
  "Generate a new draft.",
  "Compare the newest draft with the published schedule.",
];

type ChatEntry =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; text: string; response: AIChatResponse };

function unavailableMessage(error: unknown) {
  if (
    error instanceof ApiError &&
    (error.status === 0 || error.status === 502 || error.status === 503 || error.code.startsWith("AI_"))
  ) {
    return "AI Assistant is currently unavailable. Scheduling and timetable features continue to work normally.";
  }
  if (error instanceof ApiError) return error.message;
  return "The AI request could not be completed. Scheduling and timetable features continue to work normally.";
}

export function AIAssistant({
  onDraftCreated,
  onReviewDraft,
}: {
  onDraftCreated: (scheduleId: number, versionId: number) => Promise<void>;
  onReviewDraft: () => void;
}) {
  const [message, setMessage] = useState("");
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nextId = useRef(1);

  const send = async (event?: FormEvent) => {
    event?.preventDefault();
    const text = message.trim();
    if (!text || sending) return;
    setSending(true);
    setError(null);
    setMessage("");
    setEntries((current) => [...current, { id: nextId.current++, role: "user", text }]);
    try {
      const response = await aiApi.chat({ message: text });
      setEntries((current) => [
        ...current,
        { id: nextId.current++, role: "assistant", text: response.assistant_text, response },
      ]);
      if (
        response.metadata.draft_created &&
        typeof response.metadata.schedule_id === "number" &&
        typeof response.metadata.version_id === "number"
      ) {
        try {
          await onDraftCreated(response.metadata.schedule_id, response.metadata.version_id);
        } catch {
          setError("The draft was created, but schedule state could not be refreshed. Open Versions to reload it before publishing.");
        }
      }
    } catch (requestError) {
      setError(unavailableMessage(requestError));
    } finally {
      setSending(false);
    }
  };

  return (
    <section className="assistant-page">
      <header className="page-header assistant-header">
        <div>
          <p className="eyebrow">Controlled assistance</p>
          <h1>AI Assistant</h1>
          <p>Ask about school data and schedules, or request a CP-SAT-backed draft. Publishing always stays in the normal review workflow.</p>
        </div>
        <span className="assistant-safety">Cannot publish schedules</span>
      </header>

      <div className="assistant-layout">
        <div className="panel chat-panel">
          <div className="chat-log" aria-live="polite">
            {entries.length === 0 && (
              <div className="assistant-welcome">
                <span aria-hidden="true">✦</span>
                <strong>How can I help?</strong>
                <p>I use approved tools for factual answers. Timetables are generated only by CP-SAT.</p>
              </div>
            )}
            {entries.map((entry) => (
              <article className={`chat-message ${entry.role}`} key={entry.id}>
                <small>{entry.role === "user" ? "You" : "Assistant"}</small>
                <p>{entry.text}</p>
                {entry.role === "assistant" && entry.response.tool_calls.length > 0 && (
                  <div className="tool-summary">
                    <strong>Used tools</strong>
                    <ul>
                      {entry.response.tool_calls.map((tool, index) => (
                        <li key={`${tool.name}-${index}`} className={tool.success ? "" : "failed"}>
                          {tool.name}{tool.success ? "" : " (failed)"}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {entry.role === "assistant" && entry.response.metadata.draft_created && (
                  <div className="draft-review">
                    <span>Draft ready{entry.response.metadata.solver_status && ` · ${entry.response.metadata.solver_status}`}</span>
                    <button className="secondary-action" onClick={onReviewDraft}>Review draft</button>
                  </div>
                )}
              </article>
            ))}
            {sending && <div className="thinking" role="status"><span className="spinner large" /> Assistant is thinking and may use approved tools…</div>}
          </div>
          {error && <div className="assistant-error" role="alert">{error}</div>}
          <form className="chat-composer" onSubmit={(event) => void send(event)}>
            <label htmlFor="assistant-message">Message</label>
            <textarea id="assistant-message" value={message} maxLength={MAX_MESSAGE_LENGTH} disabled={sending} onChange={(event) => setMessage(event.target.value)} placeholder="Ask about teachers, schedules, or create a draft…" rows={3} />
            <div>
              <small>{message.length}/{MAX_MESSAGE_LENGTH}</small>
              <button className="primary-action" disabled={sending || !message.trim()} type="submit">{sending ? "Sending…" : "Send"}</button>
            </div>
          </form>
        </div>

        <aside className="panel prompt-panel">
          <div className="panel-heading"><div><h2>Try asking</h2><p>Examples use the current demo schedule automatically.</p></div></div>
          <div className="example-prompts">
            {examples.map((prompt) => <button disabled={sending} key={prompt} onClick={() => setMessage(prompt)}>{prompt}</button>)}
          </div>
          <div className="assistant-note"><strong>Review before publishing</strong><p>The assistant can create drafts, but only you can publish from Versions.</p></div>
        </aside>
      </div>
    </section>
  );
}
