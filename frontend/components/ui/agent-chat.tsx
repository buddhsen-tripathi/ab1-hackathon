"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  CaretDown,
  CircleNotch,
  PaperPlaneRight,
  Sparkle,
  Stop,
  TrashSimple,
} from "@phosphor-icons/react";
import { API_BASE } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Msg {
  role: "user" | "assistant";
  content: string;
}

const SUGGESTIONS = [
  "Summarize this run for a biller in 3 bullets",
  "Which facility has the most auto-accepts?",
  "Top reasons patients are flagged for review",
  "Why is wound depth missing so often?",
];

function Bubble({ msg, busy }: { msg: Msg; busy?: boolean }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] whitespace-pre-wrap rounded-lg px-3.5 py-2 text-sm leading-relaxed",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground",
        )}
      >
        {msg.content || (busy && (
          <CircleNotch className="h-4 w-4 animate-spin text-muted-foreground" />
        ))}
      </div>
    </div>
  );
}

export function AgentChat() {
  const [messages, setMessages] = React.useState<Msg[]>([]);
  const [input, setInput] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [open, setOpen] = React.useState(true);
  const [mounted, setMounted] = React.useState(false);
  const taRef = React.useRef<HTMLTextAreaElement>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const abortRef = React.useRef<AbortController | null>(null);

  // Reveal the dock shortly after the page settles, then animate it in.
  React.useEffect(() => {
    const t = setTimeout(() => setMounted(true), 350);
    return () => clearTimeout(t);
  }, []);

  React.useEffect(() => {
    const ta = taRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
    }
  }, [input]);

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setOpen(true);
    const history = [...messages, { role: "user", content: trimmed } as Msg];
    setMessages([...history, { role: "assistant", content: "" }]);
    setInput("");
    setBusy(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) throw new Error(`${res.status} ${res.statusText}`);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = dec.decode(value, { stream: true });
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          copy[copy.length - 1] = { role: "assistant", content: last.content + chunk };
          return copy;
        });
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setMessages((prev) => {
          const copy = [...prev];
          copy[copy.length - 1] = {
            role: "assistant",
            content: `Sorry, I couldn't reach the agent (${(e as Error).message}). Is the backend running at ${API_BASE}?`,
          };
          return copy;
        });
      }
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  };

  const stop = () => abortRef.current?.abort();
  const clear = () => {
    abortRef.current?.abort();
    setMessages([]);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  const hasMsgs = messages.length > 0;

  if (!mounted) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="fixed inset-x-0 bottom-4 z-40 flex justify-center px-4"
    >
      <div className="relative w-full max-w-3xl rounded-2xl border border-border bg-card/95 shadow-xl ring-1 ring-black/[0.02] backdrop-blur supports-[backdrop-filter]:bg-card/80">
        {/* subtle top accent, the bolt "glow" rendered with our tokens */}
        <div
          className="pointer-events-none absolute -top-px left-1/2 h-px w-40 -translate-x-1/2 bg-gradient-to-r from-transparent via-primary/40 to-transparent"
          aria-hidden
        />

        {/* Messages */}
        {hasMsgs && open && (
          <div className="border-b border-border">
            <div className="flex items-center justify-between px-4 py-2">
              <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Sparkle className="h-3.5 w-3.5" weight="fill" /> Pipeline assistant
              </span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={clear}
                  title="Clear conversation"
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                >
                  <TrashSimple className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  title="Collapse"
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                >
                  <CaretDown className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
            <div ref={scrollRef} className="no-scrollbar max-h-[42vh] space-y-3 overflow-y-auto px-4 pb-4">
              {messages.map((m, i) => (
                <Bubble key={i} msg={m} busy={busy && i === messages.length - 1} />
              ))}
            </div>
          </div>
        )}

        {/* Empty-state suggestions */}
        {!hasMsgs && (
          <div className="flex flex-wrap gap-2 px-3 pt-3">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => send(s)}
                className="rounded-full border border-border bg-muted/40 px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Composer */}
        <div className="p-3">
          <div className="flex items-end gap-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Sparkle className="h-4 w-4" weight="fill" />
            </div>
            <textarea
              ref={taRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="Ask about the pipeline, the data, or a routing decision..."
              className="max-h-40 min-h-[36px] flex-1 resize-none bg-transparent py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
            />
            {busy ? (
              <button
                type="button"
                onClick={stop}
                title="Stop"
                className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-foreground transition-colors hover:bg-accent"
              >
                <Stop className="h-4 w-4" weight="fill" />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => send(input)}
                disabled={!input.trim()}
                title="Send"
                className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-all hover:bg-primary/90 active:scale-95 disabled:opacity-40 disabled:pointer-events-none"
              >
                <PaperPlaneRight className="h-4 w-4" weight="fill" />
              </button>
            )}
          </div>
          <div className="mt-1.5 flex items-center gap-2 pl-10">
            <span className="text-[11px] text-muted-foreground/70">
              Grounded on the live pipeline snapshot · Enter to send, Shift+Enter for a new line
            </span>
            {!open && hasMsgs && (
              <button
                type="button"
                onClick={() => setOpen(true)}
                className="ml-auto text-[11px] text-primary hover:underline"
              >
                Show conversation
              </button>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
