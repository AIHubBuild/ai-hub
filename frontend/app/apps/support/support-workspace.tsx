"use client";

import Link from "next/link";
import ReactMarkdown, { Components } from "react-markdown";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../components/auth/auth-provider";
import { ApiError } from "../../lib/api";
import { ChatSupportIcon, SendIcon } from "../../components/icons";
import {
  SendMessageResult,
  SupportMessage,
  TicketData,
  createSupportSession,
  fetchSupportSession,
  listSupportSessions,
  sendSupportMessage,
} from "../../lib/support";

type Stage = "start" | "working" | "done";

// Safe Markdown renderer: react-markdown escapes raw HTML by default;
// we only style the supported element set. No dangerouslySetInnerHTML.
const MARKDOWN_COMPONENTS: Components = {
  h3: ({ children }) => (
    <h3 className="mb-1.5 mt-4 text-sm font-semibold text-ink first:mt-0">
      {children}
    </h3>
  ),
  p: ({ children }) => <p className="my-1.5 leading-6">{children}</p>,
  ul: ({ children }) => (
    <ul className="my-2 list-disc space-y-1 pl-5 marker:text-muted">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2 list-decimal space-y-1.5 pl-5 marker:font-semibold marker:text-accent">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="pl-0.5 leading-6">{children}</li>,
  strong: ({ children }) => (
    <strong className="font-semibold text-ink">{children}</strong>
  ),
  em: ({ children }) => <em>{children}</em>,
  code: ({ children }) => (
    <code className="rounded bg-surface-muted px-1 py-0.5 font-mono text-[0.85em] text-ink">
      {children}
    </code>
  ),
};

const SUGGESTED_PROMPTS = [
  "My VPN won't connect",
  "I can't access the shared drive",
  "My laptop keeps restarting",
  "I need a password reset",
];

const ISSUE_TYPE_LABELS: Record<string, string> = {
  password_reset: "Password reset",
  vpn_issue: "VPN connection",
  network_issue: "Network connectivity",
  hardware_issue: "Hardware or device",
  access_issue: "Access problem",
  security_issue: "Security concern",
  email_issue: "Email problem",
  printer_issue: "Printer problem",
  m365_issue: "Microsoft 365",
  active_directory_issue: "Active Directory",
  general: "General IT support",
};

function issueTypeLabel(type: string): string {
  return ISSUE_TYPE_LABELS[type] ?? type;
}

const TICKET_STATUS_STYLES: Record<string, string> = {
  Open: "text-accent",
  "In Progress": "text-ink",
  "Awaiting Confirmation": "text-ink",
  "Escalation Requested": "text-danger",
  Resolved: "text-success",
  Escalated: "text-danger",
};

function ticketStatusStyle(status: string): string {
  return TICKET_STATUS_STYLES[status] ?? TICKET_STATUS_STYLES["Open"];
}

export function SupportWorkspace() {
  const { session, loading: authLoading } = useAuth();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<SupportMessage[]>([]);
  const [ticket, setTicket] = useState<TicketData | null>(null);
  const [issueType, setIssueType] = useState<string | null>(null);
  const [resolved, setResolved] = useState(false);
  const [stage, setStage] = useState<Stage>("start");
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [errorIsAuth, setErrorIsAuth] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const restoreAttempted = useRef(false);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (authLoading || session === null || restoreAttempted.current) {
      return;
    }
    restoreAttempted.current = true;
    listSupportSessions()
      .then((sessions) => {
        if (sessions.length === 0) {
          return;
        }
        return fetchSupportSession(sessions[0].session_id).then((detail) => {
          setSessionId(detail.session_id);
          setMessages(detail.messages);
          setTicket(detail.ticket);
          setIssueType(detail.issue_type);
          setResolved(detail.status === "resolved");
          setStage("done");
        });
      })
      .catch(() => {
        // Restore is best-effort; the user can simply start a new session.
      });
  }, [authLoading, session]);

  async function startSession() {
    setError(null);
    setErrorIsAuth(false);
    setStage("working");
    try {
      const id = await createSupportSession();
      setSessionId(id);
      setMessages([]);
      setTicket(null);
      setIssueType(null);
      setResolved(false);
      setStage("done");
    } catch (caught) {
      handleError(caught);
    }
  }

  async function startSessionWith(message: string) {
    setError(null);
    setErrorIsAuth(false);
    setStage("working");
    try {
      const id = await createSupportSession();
      setSessionId(id);
      setMessages([{ role: "user", content: message }]);
      setTicket(null);
      setIssueType(null);
      setResolved(false);
      const result: SendMessageResult = await sendSupportMessage(id, message);
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.response },
      ]);
      setTicket(result.ticket);
      setIssueType(result.issue_type);
      setResolved(result.status === "resolved");
      setStage("done");
    } catch (caught) {
      setInput(message);
      handleError(caught);
    }
  }

  function handleError(caught: unknown) {
    const isAuth =
      caught instanceof ApiError && (caught.status === 401 || caught.status === 403);
    setErrorIsAuth(isAuth);
    setError(caught instanceof Error ? caught.message : "Unexpected error.");
    setStage("start");
  }

  async function handleSend(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = input.trim();
    if (!message || sessionId === null) {
      return;
    }
    setInput("");
    setError(null);
    setErrorIsAuth(false);
    setStage("working");

    setMessages((current) => [...current, { role: "user", content: message }]);
    try {
      const result: SendMessageResult = await sendSupportMessage(
        sessionId,
        message,
      );
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.response },
      ]);
      setTicket(result.ticket);
      setIssueType(result.issue_type);
      setResolved(result.status === "resolved");
      setStage("done");
    } catch (caught) {
      handleError(caught);
      setInput(message);
      setMessages((current) =>
        current.filter(
          (entry, index) =>
            index !== current.length - 1 ||
            entry.role !== "user" ||
            entry.content !== message,
        ),
      );
    }
  }

  if (authLoading) {
    return (
      <div className="flex min-h-48 items-center justify-center rounded-[28px] bg-surface ring-1 ring-line/80">
        <div
          aria-hidden="true"
          className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-accent"
        />
      </div>
    );
  }

  if (session === null) {
    return (
      <div className="rounded-[28px] bg-surface p-8 text-center ring-1 ring-line/80 sm:p-10">
        <h2 className="ui-display text-2xl text-ink">
          Sign in to use the IT Support Copilot
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
          Support sessions and tickets are private to your account. Sign in
          to describe your IT issue and get troubleshooting guidance.
        </p>
        <Link
          href="/login?redirect=/apps/support"
          className="ui-button ui-button-primary mt-5"
        >
          Sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-[28px] bg-surface ring-1 ring-line/80">
      <div className="grid lg:grid-cols-[minmax(0,1fr)_320px]">
        <section
          aria-label="Support conversation"
          className="flex min-h-[36rem] flex-col border-b border-line lg:border-b-0 lg:border-r"
        >
          <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
            <h2 className="flex min-w-0 items-center gap-2.5 text-sm font-semibold text-ink">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ink text-canvas">
                <ChatSupportIcon className="h-4 w-4" />
              </span>
              <span className="truncate">Support session</span>
            </h2>
            <div className="flex items-center gap-4">
              {ticket !== null && (
                <span className="hidden font-mono text-[11px] text-muted sm:inline">
                  {ticket.ticket_id}
                </span>
              )}
              {sessionId !== null && (
                <button
                  type="button"
                  onClick={startSession}
                  className="shrink-0 text-sm font-medium text-muted transition-colors hover:text-ink focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                >
                  Start new
                </button>
              )}
            </div>
          </div>

          <div className="flex-1 space-y-5 overflow-y-auto bg-canvas/35 px-4 py-6 sm:px-6">
            {sessionId === null ? (
              <div className="flex h-full min-h-[28rem] flex-col justify-center">
                <p className="ui-eyebrow">New session</p>
                <h3 className="ui-display mt-3 text-3xl text-ink">
                  What is not working?
                </h3>
                <p className="mt-3 max-w-md text-sm leading-6 text-muted">
                  Describe the issue in your own words. You will get clear,
                  low-risk steps and a ticket that tracks the outcome.
                </p>
                <div className="mt-7">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">
                    Start with a common issue
                  </p>
                  <ul className="mt-3 flex max-w-lg flex-wrap gap-2">
                    {SUGGESTED_PROMPTS.map((prompt) => (
                      <li key={prompt}>
                        <button
                          type="button"
                          onClick={() => startSessionWith(prompt)}
                          disabled={stage === "working"}
                          className="rounded-full border border-line bg-surface px-3.5 py-2 text-xs font-medium text-ink-soft transition-colors hover:border-ink/30 hover:text-ink disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                        >
                          {prompt}
                        </button>
                      </li>
                    ))}
                  </ul>
                  <button
                    type="button"
                    onClick={startSession}
                    disabled={stage === "working"}
                    className="ui-button ui-button-secondary mt-5"
                  >
                    {stage === "working"
                      ? "Starting…"
                      : "Start a blank session"}
                  </button>
                </div>
              </div>
            ) : (
              <>
                {messages.map((message, index) =>
                  message.role === "user" ? (
                    <div key={index} className="flex justify-end">
                      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-ink px-4 py-2.5 text-sm leading-6 text-canvas shadow-sm sm:max-w-[75%]">
                        <span className="whitespace-pre-wrap">
                          {message.content}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div key={index} className="flex gap-3">
                      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent">
                        <ChatSupportIcon className="h-4 w-4" />
                      </span>
                      <div className="min-w-0 max-w-[88%] text-sm text-ink-soft sm:max-w-[82%]">
                        <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
                          Support engineer
                        </p>
                        <AssistantMessageContent content={message.content} />
                      </div>
                    </div>
                  ),
                )}
                {stage === "working" && (
                  <div className="flex gap-3">
                    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent">
                      <ChatSupportIcon className="h-4 w-4" />
                    </span>
                    <p className="flex items-center gap-1.5 pt-1.5 text-sm text-muted">
                      Reviewing your issue
                      <span aria-hidden="true" className="inline-flex gap-0.5">
                        <span className="h-1 w-1 animate-bounce rounded-full bg-accent [animation-delay:0ms]" />
                        <span className="h-1 w-1 animate-bounce rounded-full bg-accent [animation-delay:150ms]" />
                        <span className="h-1 w-1 animate-bounce rounded-full bg-accent [animation-delay:300ms]" />
                      </span>
                    </p>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {error !== null && (
            <div className="border-t border-line px-5 py-3">
              <p className="text-sm leading-6 text-danger">{error}</p>
              {errorIsAuth && (
                <Link
                  href="/login?redirect=/apps/support"
                  className="mt-1 inline-block text-sm font-semibold text-danger underline underline-offset-2"
                >
                  Sign in again
                </Link>
              )}
            </div>
          )}

          {sessionId !== null && (
            <form
              onSubmit={handleSend}
              className="flex items-center gap-2.5 border-t border-line px-4 py-4 sm:px-5"
            >
              <input
                aria-label="Describe your IT issue"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder={
                  resolved
                    ? "This ticket is resolved. Say thanks or start a new session."
                    : "Describe your IT issue"
                }
                maxLength={4000}
                className="ui-field"
              />
              <button
                type="submit"
                disabled={stage === "working" || input.trim().length === 0}
                className="ui-button ui-button-primary shrink-0"
              >
                <SendIcon />
                <span className="hidden sm:inline">Send</span>
              </button>
            </form>
          )}
          {sessionId !== null && (
            <p className="border-t border-line px-5 py-3 text-xs leading-5 text-muted">
              The Copilot uses the AI Hub knowledge base for your issue
              category. When it has no relevant guidance, it says so.
            </p>
          )}
        </section>

        <aside aria-label="Ticket details" className="bg-surface-muted/55 p-6">
          <div className="flex items-center justify-between gap-3">
            <h2 className="ui-eyebrow">Ticket</h2>
            {ticket !== null && (
              <span
                className={`inline-flex items-center gap-1.5 text-xs font-medium ${ticketStatusStyle(ticket.status)}`}
              >
                <span
                  aria-hidden="true"
                  className="h-1.5 w-1.5 rounded-full bg-current"
                />
                {ticket.status}
              </span>
            )}
          </div>

          {ticket === null ? (
            <p className="mt-4 text-sm leading-6 text-muted">
              A ticket is created after your first message. Priority, owner,
              and status stay visible here without crowding the conversation.
            </p>
          ) : (
            <dl className="mt-5 divide-y divide-line text-sm">
              <div className="flex items-center justify-between gap-3 py-3 first:pt-0">
                <dt className="text-muted">Reference</dt>
                <dd className="font-mono text-xs font-medium text-ink">
                  {ticket.ticket_id}
                </dd>
              </div>
              {issueType !== null && (
                <div className="py-3">
                  <dt className="text-muted">Issue</dt>
                  <dd className="mt-1 font-medium text-ink">
                    {issueTypeLabel(issueType)}
                  </dd>
                </div>
              )}
              <div className="py-3">
                <dt className="text-muted">Priority</dt>
                <dd className="mt-1 font-medium text-ink">
                  {ticket.priority}
                </dd>
              </div>
              <div className="py-3">
                <dt className="text-muted">Assigned team</dt>
                <dd className="mt-1 font-medium text-ink">
                  {ticket.assigned_team}
                </dd>
              </div>
              <div className="grid grid-cols-2 gap-3 py-3">
                <div>
                  <dt className="text-muted">Attempts</dt>
                  <dd className="mt-1 font-medium text-ink">
                    {ticket.troubleshooting_attempts ?? 0}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">Handoff</dt>
                  <dd className="mt-1 font-medium text-ink">
                    {(ticket.handoff_status ?? "not_requested")
                      .replace(/_/g, " ")}
                  </dd>
                </div>
              </div>
              {ticket.reported_issue ? (
                <div className="py-3">
                  <dt className="text-muted">Reported issue</dt>
                  <dd className="mt-1 line-clamp-3 text-ink">
                    {ticket.reported_issue}
                  </dd>
                </div>
              ) : null}
              {ticket.latest_user_update ? (
                <div className="py-3">
                  <dt className="text-muted">Latest update</dt>
                  <dd className="mt-1 line-clamp-3 text-ink">
                    {ticket.latest_user_update}
                  </dd>
                </div>
              ) : null}
              {ticket.current_hypothesis &&
              ticket.current_hypothesis !== "Not confirmed" ? (
                <div className="py-3">
                  <dt className="text-muted">Recorded summary</dt>
                  <dd className="mt-1 whitespace-pre-line text-ink">
                    {ticket.current_hypothesis}
                  </dd>
                </div>
              ) : null}
              {ticket.escalation_reason ? (
                <div className="py-3 last:pb-0">
                  <dt className="text-muted">Escalation reason</dt>
                  <dd className="mt-1 text-ink">{ticket.escalation_reason}</dd>
                </div>
              ) : null}
            </dl>
          )}

          <p className="mt-6 border-t border-line pt-4 text-xs leading-5 text-muted">
            {ticket?.status === "Escalation Requested"
              ? "An escalation has been requested. No human engineer has accepted the ticket yet."
              : "The ticket updates automatically as the conversation moves toward resolution or escalation."}
          </p>
        </aside>
      </div>
    </div>
  );
}

function parseSections(content: string): { heading: string; body: string }[] {
  const sections: { heading: string; body: string }[] = [];
  let current: { heading: string; body: string[] } | null = null;
  const intro: string[] = [];
  for (const line of content.split("\n")) {
    const match = line.match(/^###\s+(.+)$/);
    if (match) {
      if (current) {
        sections.push({ heading: current.heading, body: current.body.join("\n") });
      }
      current = { heading: match[1].trim(), body: [] };
    } else if (current) {
      current.body.push(line);
    } else {
      intro.push(line);
    }
  }
  if (current) {
    sections.push({ heading: current.heading, body: current.body.join("\n") });
  }
  const introText = intro.join("\n").trim();
  if (introText) {
    sections.unshift({ heading: "", body: introText });
  }
  return sections;
}

function MarkdownBody({ text }: { text: string }) {
  return (
    <ReactMarkdown components={MARKDOWN_COMPONENTS}>
      {text.trim() || " "}
    </ReactMarkdown>
  );
}

function AssistantMessageContent({ content }: { content: string }) {
  const sections = parseSections(content);
  if (sections.length === 0) {
    return <MarkdownBody text={content} />;
  }
  return (
    <div className="space-y-3">
      {sections.map((section, index) => {
        const heading = section.heading.toLowerCase();
        const body = section.body.trim();

        if (heading === "" || heading.includes("troubleshooting response")) {
          return <MarkdownBody key={index} text={body || section.heading} />;
        }

        if (heading.includes("issue classification")) {
          const raw = body || section.heading;
          return (
            <p
              key={index}
              className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent"
            >
              Issue: {issueTypeLabel(raw)}
            </p>
          );
        }

        if (heading.includes("follow-up question")) {
          if (body === "No follow-up question") {
            return (
              <p key={index} className="text-xs text-muted">
                No follow-up question
              </p>
            );
          }
          return (
            <div
              key={index}
              className="border-l-2 border-accent bg-accent-soft/45 px-4 py-3"
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-accent">
                Follow-up question
              </p>
              <MarkdownBody text={body} />
            </div>
          );
        }

        if (heading.includes("root cause analysis")) {
          if (body === "Pending resolution") {
            return (
              <p key={index} className="text-xs text-muted">
                Root cause: pending resolution
              </p>
            );
          }
          return (
            <div
              key={index}
              className="border-l-2 border-ink bg-surface-muted px-4 py-3"
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink">
                Root cause analysis
              </p>
              <MarkdownBody text={body} />
            </div>
          );
        }

        if (heading.includes("escalation status")) {
          const escalated = body.toLowerCase().includes("escalated to");
          return (
            <p
              key={index}
              className={`inline-flex items-center gap-2 text-xs font-medium ${
                escalated ? "text-danger" : "text-muted"
              }`}
            >
              <span
                aria-hidden="true"
                className="h-1.5 w-1.5 rounded-full bg-current"
              />
              {body}
            </p>
          );
        }

        if (heading.includes("support ticket")) {
          const entries: [string, string][] = [];
          for (const line of body.split("\n")) {
            const match = line.match(/^-\s*([^:]+):\s*(.+)$/);
            if (match) {
              entries.push([match[1].trim(), match[2].trim()]);
            }
          }
          if (entries.length === 0) {
            return <MarkdownBody key={index} text={body} />;
          }
          return (
            <div
              key={index}
              className="border-t border-line pt-3 text-xs"
            >
              {entries.map(([key, value]) => (
                <p key={key}>
                  <span className="text-muted">{key}:</span>{" "}
                  <span className="font-medium text-ink">
                    {value}
                  </span>
                </p>
              ))}
            </div>
          );
        }

        return (
          <div key={index}>
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
              {section.heading}
            </p>
            <MarkdownBody text={body} />
          </div>
        );
      })}
    </div>
  );
}
