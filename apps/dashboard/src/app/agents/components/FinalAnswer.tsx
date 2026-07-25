"use client";

import {
  BookOpen,
  CheckCircle2,
  Copy,
  FileText,
} from "lucide-react";

import {
  useState,
} from "react";

import type {
  AgentSource,
} from "../types";


type FinalAnswerProps = {
  answer: string;
  sources: AgentSource[];
};


function getSourceTitle(
  source: AgentSource,
  index: number,
): string {
  return (
    source.title ??
    source.filename ??
    source.document_id ??
    `Source ${index + 1}`
  );
}


export default function FinalAnswer({
  answer,
  sources,
}: FinalAnswerProps) {
  const [copied, setCopied] =
    useState(false);

  async function handleCopy(): Promise<void> {
    if (!answer) {
      return;
    }

    await navigator.clipboard.writeText(
      answer,
    );

    setCopied(true);

    window.setTimeout(() => {
      setCopied(false);
    }, 1600);
  }

  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 sm:p-6">
      <div className="flex flex-col gap-4 border-b border-white/10 pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-400">
            Agent Response
          </p>

          <h2 className="mt-2 text-xl font-semibold text-white">
            Final answer
          </h2>

          <p className="mt-1 text-sm leading-6 text-slate-400">
            The completed response generated from
            the selected agent&apos;s execution.
          </p>
        </div>

        <button
          type="button"
          disabled={!answer}
          onClick={() => {
            void handleCopy();
          }}
          className={[
            "inline-flex w-fit items-center justify-center gap-2 rounded-xl border px-3.5 py-2",
            "text-sm font-medium transition",
            answer
              ? "border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/[0.05] hover:text-white"
              : "cursor-not-allowed border-white/5 text-slate-600",
          ].join(" ")}
        >
          {copied ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-300" />
          ) : (
            <Copy className="h-4 w-4" />
          )}

          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      {answer ? (
        <div className="mt-5 rounded-xl border border-white/10 bg-black/20 p-4 sm:p-5">
          <div className="whitespace-pre-wrap text-sm leading-7 text-slate-200">
            {answer}
          </div>
        </div>
      ) : (
        <div className="mt-5 flex min-h-56 flex-col items-center justify-center rounded-xl border border-dashed border-white/10 bg-black/10 px-6 py-10 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-slate-400">
            <FileText className="h-5 w-5" />
          </div>

          <h3 className="mt-4 font-medium text-slate-200">
            No answer yet
          </h3>

          <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
            The agent&apos;s final response will
            appear here after execution completes.
          </p>
        </div>
      )}

      {sources.length > 0 && (
        <div className="mt-6">
          <div className="mb-3 flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-cyan-300" />

            <h3 className="text-sm font-semibold text-white">
              Sources
            </h3>
          </div>

          <div className="grid gap-3">
            {sources.map((source, index) => (
              <article
                key={`${getSourceTitle(
                  source,
                  index,
                )}-${index}`}
                className="rounded-xl border border-white/10 bg-black/20 p-4"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h4 className="text-sm font-medium text-slate-200">
                      {getSourceTitle(
                        source,
                        index,
                      )}
                    </h4>

                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                      {typeof source.page ===
                        "number" && (
                        <span>
                          Page {source.page}
                        </span>
                      )}

                      {typeof source.score ===
                        "number" && (
                        <span>
                          Score{" "}
                          {source.score.toFixed(3)}
                        </span>
                      )}

                      {typeof source.chunk_index ===
                        "number" && (
                        <span>
                          Chunk{" "}
                          {source.chunk_index}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {source.content && (
                  <p className="mt-3 text-sm leading-6 text-slate-400">
                    {source.content}
                  </p>
                )}
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
