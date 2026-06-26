"use client";
import Link from "next/link";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { PageHead, Loading, ErrorNote } from "@/components/Bits";
import { Glyph } from "@/components/Icon";

export default function PartnersPage() {
  const { data, error, loading } = useFetch(() => api.partners(), []);

  return (
    <>
      <PageHead eyebrow="04 · Партнёры" title="Клиники-партнёры" />
      {loading && <Loading />}
      {error && <ErrorNote error={error} />}
      {data && (
        <div className="grid3">
          {data.map((p) => (
            <Link key={p.id} href={`/partners/${p.id}?name=${encodeURIComponent(p.display_name)}`} className="panel pad" style={{ display: "block" }}>
              <div className="between">
                <span className="badge ink">{p.code}</span>
                {p.is_active ? <span className="badge green">активен</span> : <span className="badge">архив</span>}
              </div>
              <h3 style={{ marginTop: 12 }}>{p.display_name}</h3>
              <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                {p.legal_name || "юр. лицо не указано"}
              </div>
              <div className="row" style={{ marginTop: 14, gap: 6, color: "var(--accent)", fontSize: 13 }}>
                прайс клиники <Glyph.arrow size={14} />
              </div>
            </Link>
          ))}
          {data.length === 0 && <div className="empty">Партнёров пока нет</div>}
        </div>
      )}
    </>
  );
}
