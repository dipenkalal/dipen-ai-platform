import {
  Bot,
  BrainCircuit,
  Cpu,
  Database,
  FolderKanban,
  HardDrive,
  MemoryStick,
  Server,
  Settings,
  Box,
} from "lucide-react";

const stats = [
  {
    title: "Processor",
    value: "Intel Core i7-4790",
    subtitle: "4 Cores • 8 Threads",
    icon: Cpu,
  },
  {
    title: "Memory",
    value: "12 GB",
    subtitle: "DDR3",
    icon: MemoryStick,
  },
  {
    title: "Storage",
    value: "1.25 TB",
    subtitle: "SSD + HDD",
    icon: HardDrive,
  },
  {
    title: "AI Model",
    value: "Qwen3 1.7B",
    subtitle: "Thinking Off",
    icon: BrainCircuit,
  },
];

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
  return (
    <main className="min-h-screen bg-[#090B10] text-white">
      <div className="max-w-7xl mx-auto px-8 py-10">

        <header className="flex flex-col gap-6 border-b border-zinc-800 pb-8 md:flex-row md:items-center md:justify-between">

          <div>
            <div className="flex items-center gap-2 text-cyan-400 text-sm">
              <Server size={16} />
              Local AI Platform Online
            </div>

            <h1 className="text-5xl font-bold mt-3">
              Dipen AI Platform
            </h1>

            <p className="text-zinc-400 mt-4 max-w-2xl">
              Your private AI operating platform for local models,
              knowledge management, projects, research,
              automation and learning.
            </p>
          </div>

          <div className="bg-green-500/10 border border-green-500/20 rounded-full px-5 py-2 text-green-300 text-sm">
            ● DAP Online
          </div>

        </header>

        <section className="mt-10">

          <h2 className="text-2xl font-semibold mb-6">
            Infrastructure
          </h2>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">

            {stats.map((card) => (

              <div
                key={card.title}
                className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6"
              >

                <div className="flex justify-between">

                  <div>

                    <p className="text-zinc-500 text-sm">
                      {card.title}
                    </p>

                    <h3 className="text-xl font-bold mt-2">
                      {card.value}
                    </h3>

                  </div>

                  <card.icon
                    size={28}
                    className="text-cyan-400"
                  />

                </div>

                <p className="text-zinc-500 text-sm mt-6">
                  {card.subtitle}
                </p>

              </div>

            ))}

          </div>

        </section>

        <section className="mt-14">

          <h2 className="text-2xl font-semibold mb-6">
            Quick Access
          </h2>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">

            {modules.map((item) => (

              <a
                href={item.link}
                target="_blank"
                key={item.title}
                className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 hover:border-cyan-500 transition"
              >

                <item.icon
                  size={34}
                  className="text-cyan-400"
                />

                <h3 className="mt-6 text-xl font-semibold">
                  {item.title}
                </h3>

                <p className="text-zinc-400 mt-3">
                  {item.description}
                </p>

                <div className="mt-8 flex justify-between items-center">

                  <span className="text-cyan-400">
                    Open →
                  </span>

                  <span className="text-xs text-zinc-500">
                    {item.status}
                  </span>

                </div>

              </a>

            ))}

          </div>

        </section>

        <section className="mt-14 grid grid-cols-1 gap-6 lg:grid-cols-3">

          <div className="lg:col-span-2 bg-zinc-900 rounded-2xl border border-zinc-800 p-6">

            <h2 className="text-xl font-semibold">
              Recent Projects
            </h2>

            <div className="mt-6 space-y-4">

              {[
                "Dipen AI Platform",
                "AWS Three Tier Infrastructure",
                "Docker Learning Lab",
                "Terraform Practice"
              ].map((project) => (

                <div
                  key={project}
                  className="flex justify-between border-b border-zinc-800 pb-3"
                >

                  <span>{project}</span>

                  <span className="text-zinc-500">
                    Open →
                  </span>

                </div>

              ))}

            </div>

          </div>

          <div className="bg-gradient-to-br from-cyan-600/20 to-blue-600/10 rounded-2xl border border-cyan-500/20 p-6">

            <BrainCircuit
              size={34}
              className="text-cyan-400"
            />

            <p className="mt-8 text-cyan-300 text-sm">
              ACTIVE MODEL
            </p>

            <h2 className="text-3xl font-bold mt-2">
              Qwen3 1.7B
            </h2>

            <p className="mt-5 text-zinc-400">
              Fast local model optimized for
              your Acer AI Server.
            </p>

            <div className="mt-8 text-green-400">
              ● Ollama Connected
            </div>

          </div>

        </section>

        <footer className="mt-16 border-t border-zinc-800 pt-8 text-zinc-500 text-sm">

          Dipen AI Platform v0.1 • Local First AI Operating Platform

        </footer>

      </div>
    </main>
  );
}