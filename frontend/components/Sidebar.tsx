"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Glyph } from "./Icon";

const NAV = [
  { href: "/", idx: "01", label: "Сводка", icon: Glyph.board },
  { href: "/search", idx: "02", label: "Поиск", icon: Glyph.find },
  { href: "/services", idx: "03", label: "Услуги", icon: Glyph.registry },
  { href: "/partners", idx: "04", label: "Партнёры", icon: Glyph.partners },
  { sep: true as const },
  { href: "/documents", idx: "05", label: "Документы", icon: Glyph.docs },
  { href: "/review", idx: "06", label: "Верификация", icon: Glyph.review },
];

export default function Sidebar() {
  const path = usePathname();
  const isActive = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  return (
    <aside className="sidebar">
      <Link href="/" className="brand" style={{ color: "var(--ink)" }}>
        <span className="mark" aria-hidden>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 4h16v16H4zM4 12h16M12 4v8" />
          </svg>
        </span>
        <span>
          <b>MedArchive</b>
        </span>
      </Link>
      <p className="tagline">Реестр услуг и цен клиник-партнёров</p>

      <nav className="nav">
        {NAV.map((n, i) =>
          "sep" in n ? (
            <div className="sep" key={i} />
          ) : (
            <Link key={n.href} href={n.href} className={isActive(n.href) ? "active" : ""}>
              <span className="idx">{n.idx}</span>
              <span className="row" style={{ gap: 9 }}>
                <n.icon size={16} />
                {n.label}
              </span>
            </Link>
          )
        )}
      </nav>

      <div className="foot">
        <div>v0.1 · MVP</div>
        <div style={{ marginTop: 4 }}>API · FastAPI / PostgreSQL</div>
      </div>
    </aside>
  );
}
