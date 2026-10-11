"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../components/auth/auth-provider";
import { ApiError } from "../../lib/api";
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
      <div className="flex min-h-48 items-center justify-center rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div
          aria-hidden="true"
          className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-zinc-50"
        />
      </div>
    );
  }

  if (session === null) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="text-lg font-medium text-zinc-900 dark:text-zinc-50">
          Sign in to use the IT Support Copilot
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          Support sessions and tickets are private to your account. Sign in
          to describe your IT issue and get troubleshooting guidance.
        </p>
        <Link
          href="/login?redirect=/apps/support"
          className="mt-5 inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 dark:focus-visible:outline-zinc-50"
        >
          Sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
      <section
        aria-label="Support conversation"
        className="flex min-h-96 flex-col rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
      >
        <div className="flex items-center justify-between border-b border-zinc-100 px-5 py-3 dark:border-zinc-800">
          <h2 className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
            Support session
          </h2>
          {sessionId !== null && (
            <button
              type="button"
              onClick={startSession}
              className="text-sm text-zinc-500 underline-offset-2 hover:text-zinc-900 hover:underline focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:text-zinc-400 dark:hover:text-zinc-50"
            >
              Start new session
            </button>
          )}
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {sessionId === null ? (
            <div className="flex h-full min-h-64 flex-col items-center justify-center text-center">
              <p className="max-w-sm text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
                Start a support session to describe your IT issue. The
                Copilot will classify it, ask a follow-up question, and
                guide you through troubleshooting with a tracked ticket.
              </p>
              <button
                type="button"
                onClick={startSession}
                disabled={stage === "working"}
                className="mt-5 inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 dark:focus-visible:outline-zinc-50"
              >
                {stage === "working" ? "Starting…" : "Start support session"}
              </button>
            </div>
          ) : (
            <>
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] whitespace-pre-wrap rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
                      message.role === "user"
                        ? "bg-zinc-900 text-white dark:bg-zinc-50 dark:text-zinc-900"
                        : "border border-zinc-200 bg-zinc-50 text-zinc-800 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-200"
                    }`}
                  >
                    {message.content}
                  </div>
                </div>
              ))}
              {stage === "working" && (
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  The Copilot is working on this…
                </p>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {error !== null && (
          <div className="border-t border-red-100 px-5 py-3 dark:border-red-900">
            <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
            {errorIsAuth && (
              <Link
                href="/login?redirect=/apps/support"
                className="mt-1 inline-block text-sm font-medium text-red-700 underline underline-offset-2 hover:text-red-800 dark:text-red-300 dark:hover:text-red-200"
              >
                Sign in again
              </Link>
            )}
          </div>
        )}

        {sessionId !== null && !resolved && (
          <form
            onSubmit={handleSend}
            className="flex items-center gap-3 border-t border-zinc-100 px-5 py-3 dark:border-zinc-800"
          >
            <input
              aria-label="Describe your IT issue"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Describe your IT issue…"
              maxLength={4000}
              className="w-full rounded-lg border border-zinc-200 bg-zinc-50 p-2.5 text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-2 focus:outline-offset-2 focus:outline-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-500"
            />
            <button
              type="submit"
              disabled={stage === "working" || input.trim().length === 0}
              className="shrink-0 rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 dark:focus-visible:outline-zinc-50"
            >
              Send
            </button>
          </form>
        )}
      </section>

      <aside
        aria-label="Ticket details"
        className="h-fit rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
      >
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          Support ticket
        </h2>
        {ticket === null ? (
          <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
            A ticket is generated after your first message.
          </p>
        ) : (
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-500 dark:text-zinc-400">Ticket</dt>
              <dd className="font-medium text-zinc-900 dark:text-zinc-50">
                {ticket.ticket_id}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-500 dark:text-zinc-400">Status</dt>
              <dd className="font-medium text-zinc-900 dark:text-zinc-50">
                {ticket.status}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-500 dark:text-zinc-400">Priority</dt>
              <dd className="font-medium text-zinc-900 dark:text-zinc-50">
                {ticket.priority}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-500 dark:text-zinc-400">Team</dt>
              <dd className="text-right font-medium text-zinc-900 dark:text-zinc-50">
                {ticket.assigned_team}
              </dd>
            </div>
            {issueType !== null && (
              <div className="flex justify-between gap-3">
                <dt className="text-zinc-500 dark:text-zinc-400">Issue type</dt>
                <dd className="font-medium text-zinc-900 dark:text-zinc-50">
                  {issueType}
                </dd>
              </div>
            )}
          </dl>
        )}
      </aside>
    </div>
  );
}
