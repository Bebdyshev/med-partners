"use client";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { PageHead, Loading, ErrorNote } from "@/components/Bits";
import { Glyph } from "@/components/Icon";

export default function ServicesPage() {
  const [q, setQ] = useState("");
  const [applied, setApplied] = useState("");
  const { data, error, loading } = useFetch(() => api.services({ q: applied || undefined, limit: 200 }), [applied]);

  return (
    <>
      <PageHead eyebrow="03 · Справочник" title="Услуги" />

      <form
        className="field" style={{ maxWidth: 460 }}
        onSubmit={(e) => { e.preventDefault(); setApplied(q.trim()); }}
      >
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="фильтр по названию…" />
        <button className="btn" style={{ boxShadow: "none", borderLeft: "1.5px solid var(--ink)" }}>Фильтр</button>
      </form>

      <div style={{ marginTop: 20 }}>
        {loading && <Loading />}
        {error && <ErrorNote error={error} />}
        {data && (
          <div className="panel">
            <table className="table">
              <thead><tr><th style={{ width: 50 }}>#</th><th>Наименование</th><th>Категория</th><th></th></tr></thead>
              <tbody>
                {data.map((s, i) => (
                  <tr key={s.id}>
                    <td className="num muted">{i + 1}</td>
                    <td>{s.canonical_name}</td>
                    <td className="muted">{s.category || "—"}</td>
                    <td className="num">
                      <Link href={`/services/${s.id}?name=${encodeURIComponent(s.canonical_name)}`} className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
                        клиники <Glyph.arrow size={14} />
                      </Link>
                    </td>
                  </tr>
                ))}
                {data.length === 0 && <tr><td colSpan={4} className="muted" style={{ padding: 30, textAlign: "center" }}>Ничего не найдено</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
