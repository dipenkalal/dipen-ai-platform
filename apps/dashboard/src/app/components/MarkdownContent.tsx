"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { Components } from "react-markdown";

type MarkdownContentProps = {
  value: string;
  className?: string;
};

const markdownComponents: Components = {
  h1({ children }) {
    return (
      <h1 className="mb-4 mt-7 text-2xl font-semibold leading-tight text-white first:mt-0">
        {children}
      </h1>
    );
  },

  h2({ children }) {
    return (
      <h2 className="mb-3 mt-6 text-xl font-semibold leading-tight text-white first:mt-0">
        {children}
      </h2>
    );
  },

  h3({ children }) {
    return (
      <h3 className="mb-3 mt-5 text-lg font-semibold leading-snug text-white first:mt-0">
        {children}
      </h3>
    );
  },

  h4({ children }) {
    return (
      <h4 className="mb-2 mt-5 font-semibold text-slate-100 first:mt-0">
        {children}
      </h4>
    );
  },

  p({ children }) {
    return (
      <p className="my-3 leading-7 text-slate-300 first:mt-0 last:mb-0">
        {children}
      </p>
    );
  },

  ul({ children }) {
    return (
      <ul className="my-3 list-disc space-y-1.5 pl-6 text-slate-300">
        {children}
      </ul>
    );
  },

  ol({ children }) {
    return (
      <ol className="my-3 list-decimal space-y-1.5 pl-6 text-slate-300">
        {children}
      </ol>
    );
  },

  li({ children }) {
    return <li className="pl-1 leading-7">{children}</li>;
  },

  strong({ children }) {
    return <strong className="font-semibold text-slate-100">{children}</strong>;
  },

  em({ children }) {
    return <em className="text-slate-200">{children}</em>;
  },

  del({ children }) {
    return <del className="text-slate-500">{children}</del>;
  },

  blockquote({ children }) {
    return (
      <blockquote className="my-4 border-l-2 border-cyan-400/50 bg-cyan-400/[0.04] py-1 pl-4 pr-3 text-slate-400">
        {children}
      </blockquote>
    );
  },

  a({ href, children }) {
    const external = typeof href === "string" && /^https?:\/\//i.test(href);

    return (
      <a
        href={href}
        target={external ? "_blank" : undefined}
        rel={external ? "noreferrer noopener" : undefined}
        className="font-medium text-cyan-300 underline decoration-cyan-400/30 underline-offset-4 transition hover:text-cyan-200"
      >
        {children}
      </a>
    );
  },

  pre({ children }) {
    return (
      <pre className="my-4 overflow-x-auto rounded-xl border border-white/10 bg-slate-950/90 p-4 text-xs leading-6 text-slate-300">
        {children}
      </pre>
    );
  },

  code({ children, className }) {
    const rawValue = String(children);
    const isBlock =
      rawValue.includes("\n") || Boolean(className?.startsWith("language-"));

    if (isBlock) {
      return (
        <code
          className={[
            "block min-w-max bg-transparent p-0 font-mono text-xs text-slate-300",
            className ?? "",
          ].join(" ")}
        >
          {rawValue.replace(/\n$/, "")}
        </code>
      );
    }

    return (
      <code className="rounded-md border border-white/10 bg-black/30 px-1.5 py-0.5 font-mono text-[0.9em] text-cyan-200">
        {children}
      </code>
    );
  },

  table({ children }) {
    return (
      <div className="my-4 overflow-x-auto rounded-xl border border-white/10">
        <table className="w-full border-collapse text-left text-sm">
          {children}
        </table>
      </div>
    );
  },

  thead({ children }) {
    return <thead className="bg-white/[0.05] text-slate-200">{children}</thead>;
  },

  tbody({ children }) {
    return <tbody className="divide-y divide-white/10">{children}</tbody>;
  },

  tr({ children }) {
    return (
      <tr className="border-b border-white/10 last:border-b-0">{children}</tr>
    );
  },

  th({ children }) {
    return (
      <th className="whitespace-nowrap px-4 py-3 font-semibold">{children}</th>
    );
  },

  td({ children }) {
    return <td className="px-4 py-3 align-top text-slate-300">{children}</td>;
  },

  hr() {
    return <hr className="my-6 border-white/10" />;
  },
};

export default function MarkdownContent({
  value,
  className,
}: MarkdownContentProps) {
  return (
    <div
      className={["min-w-0 text-sm text-slate-300", className ?? ""].join(" ")}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={markdownComponents}
      >
        {value}
      </ReactMarkdown>
    </div>
  );
}
