"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Newspaper, Search, Radio, Cpu } from "lucide-react";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Digest", icon: Newspaper },
  { href: "/search", label: "Search", icon: Search },
  { href: "/sources", label: "Sources", icon: Radio },
];

export function Navigation() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-gray-200 bg-white/80 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-semibold text-gray-900">
          <Cpu className="h-5 w-5 text-blue-600" />
          <span>AI News</span>
        </Link>

        <nav className="flex items-center gap-1">
          {links.map(({ href, label, icon: Icon }) => {
            const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
