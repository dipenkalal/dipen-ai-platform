"use client";

import {
  Bot,
  Box,
  BrainCircuit,
  Cpu,
  Database,
  FolderKanban,
  HardDrive,
  MemoryStick,
  Server,
  Settings,
} from "lucide-react";

import { useSystemStatus } from "@/hooks/useSystemStatus";

const modules = [
  {
    title: "AI Chat",
    description: "Launch Open WebUI",
    icon: Bot,
    link: "http://192.168.40.212:3000",
    status: "Online",
  },
  {
    title: "Knowledge",
    description: "Documents, PDFs & RAG",
    icon: Database,
    link: "#",
    status: "Coming Soon",
  },
  {
    title: "Projects",
    description: "AWS • Docker • Terraform",
    icon: FolderKanban,
    link: "#",
    status: "Coming Soon",
  },
  {
    title: "Containers",
    description: "Portainer Dashboard",
    icon: Box,
    link: "https://192.168.40.212:9443",
    status: "Online",
  },
  {
    title: "Models",
    description: "Manage Local Models",
    icon: BrainCircuit,
    link: "#",
    status: "2 Installed",
  },
  {
    title: "Settings",
    description: "Platform Settings",
    icon: Settings,
    link: "#",
    status: "Coming Soon",
  },
];

export default function Home() {
  const { status, loading, error } = useSystemStatus();

  const cpuUsage = status?.system.cpu.usage_percent ?? 0;
  const memory = status?.system.memory;
  const disk = status?.system.disks.system;
  const loadedModel = status?.ollama.loaded_models[0]?.name;

  const stats = [
    {
      title: "Processor",
      value: status
        ? `${cpuUsage}%`
        : loading
          ? "Loading..."
          : "Unavailable",
      subtitle: status
        ? `${status.system.cpu.physical_cores ?? "Unknown"} cores • ${
            status.system.cpu.logical_threads ?? "Unknown"
          } threads`
        : error ?? "Waiting for API",
      icon: Cpu,
    },
    {
      title: "Memory",
      value: memory
        ? `${memory.used_gb} / ${memory.total_gb} GB`
        : loading
          ? "Loading..."
          : "Unavailable",
      subtitle: memory
        ? `${memory.percent}% used`
        : error ?? "Waiting for API",
      icon: MemoryStick,
    },
    {
      title: "Storage",
      value: disk
        ? `${disk.used_gb} / ${disk.total_gb} GB`
        : loading
          ? "Loading..."
          : "Unavailable",
      subtitle: disk ? `${disk.percent}% used` : error ?? "Waiting for API",
      icon: HardDrive,
    },
    {
      title: "AI Model",
      value:
        loadedModel ??
        (status?.ollama.online ? "No model loaded" : "Ollama offline"),
      subtitle: status?.ollama.online
        ? `${status.ollama.loaded_count} model${
            status.ollama.loaded_count === 1 ? "" : "s"
          } loaded`
        : "Ollama unavailable",
      icon: BrainCircuit,
    },
  ];

  return (
    <main className="min-h-screen bg-[#090B10] text-white">
      <div className="mx-auto max-w-7xl px-8 py-10">
        <header className="flex flex-col gap-6 border-b border-zinc-800 pb-8 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm text-cyan-400">
              <Server size={16} />
              Local AI Platform Online
            </div>

            <h1 className="mt-3 text-5xl font-bold">Dipen AI Platform</h1>

            <p className="mt-4 max-w-2xl text-zinc-400">
              Your private AI operating platform for local models, knowledge
              management, projects, research, automation and learning.
            </p>

            <p className="mt-2 text-sm text-zinc-500">
              Server uptime:{" "}
              <span className="text-zinc-300">
                {status?.system.uptime.formatted ??
                  (loading ? "Loading..." : "Unavailable")}
              </span>
            </p>
          </div>

          <div
            className={`rounded-full border px-5 py-2 text-sm ${
              error
                ? "border-red-500/20 bg-red-500/10 text-red-300"
                : "border-green-500/20 bg-green-500/10 text-green-300"
            }`}
          >
            {error ? "● DAP API Offline" : "● DAP Online"}
          </div>
        </header>

        <section className="mt-10">
          <h2 className="mb-6 text-2xl font-semibold">Infrastructure</h2>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
            {stats.map((card) => {
              const Icon = card.icon;

              return (
                <div
                  key={card.title}
                  className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6"
                >
                  <div className="flex justify-between">
                    <div>
                      <p className="text-sm text-zinc-500">{card.title}</p>

                      <h3 className="mt-2 text-xl font-bold">{card.value}</h3>
                    </div>

                    <Icon size={28} className="text-cyan-400" />
                  </div>

                  <p className="mt-6 text-sm text-zinc-500">
                    {card.subtitle}
                  </p>
                </div>
              );
            })}
          </div>
        </section>

        <section className="mt-14">
          <h2 className="mb-6 text-2xl font-semibold">Quick Access</h2>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
            {modules.map((item) => {
              const Icon = item.icon;

              return (
                <a
                  href={item.link}
                  target={item.link.startsWith("http") ? "_blank" : undefined}
                  rel={
                    item.link.startsWith("http")
                      ? "noopener noreferrer"
                      : undefined
                  }
                  key={item.title}
                  className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 transition hover:border-cyan-500"
                >
                  <Icon size={34} className="text-cyan-400" />

                  <h3 className="mt-6 text-xl font-semibold">{item.title}</h3>

                  <p className="mt-3 text-zinc-400">{item.description}</p>

                  <div className="mt-8 flex items-center justify-between">
                    <span className="text-cyan-400">Open →</span>

                    <span className="text-xs text-zinc-500">
                      {item.status}
                    </span>
                  </div>
                </a>
              );
            })}
          </div>
        </section>

        <section className="mt-14 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 lg:col-span-2">
            <h2 className="text-xl font-semibold">Recent Projects</h2>

            <div className="mt-6 space-y-4">
              {[
                "Dipen AI Platform",
                "AWS Three Tier Infrastructure",
                "Docker Learning Lab",
                "Terraform Practice",
              ].map((project) => (
                <div
                  key={project}
                  className="flex justify-between border-b border-zinc-800 pb-3"
                >
                  <span>{project}</span>
                  <span className="text-zinc-500">Open →</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-cyan-500/20 bg-gradient-to-br from-cyan-600/20 to-blue-600/10 p-6">
            <BrainCircuit size={34} className="text-cyan-400" />

            <p className="mt-8 text-sm text-cyan-300">ACTIVE MODEL</p>

            <h2 className="mt-2 text-3xl font-bold">
              {loadedModel ??
                (status?.ollama.online ? "No model loaded" : "Ollama offline")}
            </h2>

            <p className="mt-5 text-zinc-400">
              {status?.ollama.online
                ? "Local Ollama runtime is available."
                : "Ollama is currently unavailable from this API host."}
            </p>

            <div
              className={`mt-8 ${
                status?.ollama.online ? "text-green-400" : "text-red-400"
              }`}
            >
              {status?.ollama.online
                ? "● Ollama Connected"
                : "● Ollama Disconnected"}
            </div>
          </div>
        </section>

        <footer className="mt-16 border-t border-zinc-800 pt-8 text-sm text-zinc-500">
          Dipen AI Platform v0.2 • Live Infrastructure Dashboard
        </footer>
      </div>
    </main>
  );
}