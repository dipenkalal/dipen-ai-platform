"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  BarChart3,
  Bot,
  BrainCircuit,
  Building2,
  History,
  Mic,
  ServerCog,
  ShieldCheck,
} from "lucide-react";


type NavigationItem = {
  label: string;
  href: string;
  icon: React.ComponentType<{
    className?: string;
  }>;
  exact?: boolean;
};


const navigationItems: NavigationItem[] = [
  {
    label: "Guardian",
    href: "/",
    icon: ShieldCheck,
    exact: true,
  },
  {
    label: "Company",
    href: "/company",
    icon: Building2,
  },
  {
    label: "Voice",
    href: "/guardian",
    icon: Mic,
  },
  {
    label: "Knowledge",
    href: "/knowledge",
    icon: BrainCircuit,
  },
  {
    label: "Agents",
    href: "/agents",
    icon: Bot,
  },
  {
    label: "History",
    href: "/agents/history",
    icon: History,
  },
  {
    label: "Analytics",
    href: "/analytics",
    icon: BarChart3,
  },
  {
    label: "Monitoring",
    href: "/monitoring",
    icon: ServerCog,
  },
];


function isActiveRoute(
  pathname: string,
  item: NavigationItem,
): boolean {
  if (item.exact) {
    return pathname === item.href;
  }

  return (
    pathname === item.href ||
    pathname.startsWith(
      `${item.href}/`,
    )
  );
}


export function AppNavigation() {
  const pathname = usePathname();

  if (pathname === "/") {
    return null;
  }

  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-950/90 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-3"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-300/20 bg-cyan-300/[0.08] text-cyan-300">
            <span className="text-sm font-bold">
              DAP
            </span>
          </div>

          <div className="hidden sm:block">
            <p className="text-sm font-semibold text-white">
              Guardian Control Core
            </p>

            <p className="text-xs text-slate-500">
              Dipen AI Platform
            </p>
          </div>
        </Link>

        <nav
          aria-label="Primary navigation"
          className="ml-auto flex min-w-0 items-center gap-1 overflow-x-auto"
        >
          {navigationItems.map((item) => {
            const Icon = item.icon;

            const active =
              isActiveRoute(
                pathname,
                item,
              );

            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={
                  active
                    ? "page"
                    : undefined
                }
                className={[
                  "inline-flex shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition",
                  active
                    ? "bg-cyan-300 text-slate-950"
                    : "text-slate-300 hover:bg-white/[0.06] hover:text-white",
                ].join(" ")}
              >
                <Icon className="h-4 w-4" />

                <span className="hidden lg:inline">
                  {item.label}
                </span>
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}


export default AppNavigation;
