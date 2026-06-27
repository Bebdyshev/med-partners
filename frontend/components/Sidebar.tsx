"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Glyph } from "./Icon";

const NAV = [
  { href: "/dashboard", label: "Сводка", icon: Glyph.board },
  { href: "/search", label: "Поиск", icon: Glyph.find },
  { href: "/services", label: "Услуги", icon: Glyph.registry },
  { href: "/partners", label: "Партнёры", icon: Glyph.partners },
  { sep: true as const },
  { href: "/documents", label: "Документы", icon: Glyph.docs },
  { href: "/review", label: "Верификация", icon: Glyph.review },
];

export default function Sidebar() {
  const path = usePathname();
  const isActive = (href: string) => path === href || path.startsWith(href + "/");
  return (
    <aside className="sidebar">
      <Link href="/dashboard" className="brand" style={{ color: "var(--ink)" }}>
        <span className="mark" aria-hidden>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 6h6l4 6 4-6M4 18h6l4-6" />
          </svg>
        </span>
        <b>MedArchive</b>
      </Link>
      <p className="tagline">Реестр услуг и цен клиник-партнёров</p>

      <nav className="nav">
        {NAV.map((n, i) =>
          "sep" in n ? (
            <div className="sep" key={i} />
          ) : (
            <Link key={n.href} href={n.href} className={isActive(n.href) ? "active" : ""}>
              <n.icon size={17} />
              {n.label}
            </Link>
          )
        )}
      </nav>

      <div className="foot">
        <div>v0.1 · MVP</div>
        <div>FastAPI · PostgreSQL</div>
      </div>
    </aside>
  );
}
