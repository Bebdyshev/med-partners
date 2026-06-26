"use client";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { SearchResult } from "@/lib/types";
import { PageHead } from "@/components/Bits";
import { Glyph } from "@/components/Icon";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run(e?: React.FormEvent) {
    e?.preventDefault();
    if (!q.trim()) return;
    setLoading(true); setErr(null);
    try { setRes(await api.search(q.trim())); }
    catch (e) { setErr(String((e as Error).message)); }
    finally { setLoading(false); }
  }

  return (
    <>
      <PageHead eyebrow="02 · Поиск" title="Найти услугу или клинику" />

      <form className="field" onSubmit={run} style={{ maxWidth: 620 }}>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="например: кардиолог, УЗИ, дисбактериоз…" />
        <button className="btn primary" style={{ boxShadow: "none", borderLeft: "1.5px solid var(--accent-ink)" }}>
          <span className="row" style={{ gap: 7 }}><Glyph.find size={15} /> Искать</span>
        </button>
      </form>
      <div className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>
        Полнотекстовый поиск с морфологией (находит словоформы) и устойчив к опечаткам.
      </div>

      {loading && <div className="loading" style={{ marginTop: 24 }}>Поиск…</div>}
      {err && <div className="panel pad" style={{ marginTop: 20, color: "var(--oxblood)" }}>{err}</div>}

      {res && (
        <>
          <div className="section-title">Услуги · {res.services.length}</div>
          {res.services.length === 0 ? (
            <div className="empty">Ничего не найдено</div>
          ) : (
            <div className="panel">
              <table className="table">
                <thead><tr><th>Услуга</th><th>Категория</th><th style={{ width: 120 }}></th></tr></thead>
                <tbody>
                  {res.services.map((s) => (
                    <tr key={s.id}>
                      <td>{s.canonical_name}</td>
                      <td className="muted">{s.category || "—"}</td>
                      <td className="num">
                        <Link href={`/services/${s.id}?name=${encodeURIComponent(s.canonical_name)}`} className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
                          клиники <Glyph.arrow size={14} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="section-title">Партнёры · {res.partners.length}</div>
          {res.partners.length === 0 ? (
            <div className="empty">Партнёры не найдены</div>
          ) : (
            <div className="row" style={{ gap: 10 }}>
              {res.partners.map((p) => (
                <Link key={p.id} href={`/partners/${p.id}`} className="panel pad" style={{ minWidth: 200 }}>
                  <b>{p.display_name}</b>
                  <div className="muted" style={{ fontSize: 13 }}>{p.city || "город не указан"}</div>
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
