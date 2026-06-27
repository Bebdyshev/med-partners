"use client";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { SearchResult } from "@/lib/types";
import { PageHead } from "@/components/Bits";
import { Glyph } from "@/components/Icon";

const POPULAR = ["Кардиолог", "УЗИ брюшной полости", "Общий анализ крови", "МРТ", "Эндокринолог", "ЭКГ", "Гастроскопия"];

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [res, setRes] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [scope, setScope] = useState<"all" | "services" | "partners">("all");
  const [cat, setCat] = useState<string | null>(null);
  const [city, setCity] = useState<string | null>(null);

  async function run(term?: string) {
    const t = (term ?? q).trim();
    if (!t) return;
    setQ(t); setQuery(t); setLoading(true); setErr(null);
    setScope("all"); setCat(null); setCity(null);
    try { setRes(await api.search(t)); }
    catch (e) { setErr(String((e as Error).message)); }
    finally { setLoading(false); }
  }

  const cats = res ? Array.from(new Set(res.services.map((s) => s.category).filter(Boolean) as string[])) : [];
  const cities = res ? Array.from(new Set(res.partners.map((p) => p.city).filter(Boolean) as string[])) : [];
  const services = (res?.services || []).filter((s) => !cat || s.category === cat);
  const partners = (res?.partners || []).filter((p) => !city || p.city === city);

  return (
    <>
      <PageHead eyebrow="Поиск" title="Найти услугу или клинику" />

      <form className="searchbar" onSubmit={(e) => { e.preventDefault(); run(); }}>
        <span className="sb-ic"><Glyph.find size={18} /></span>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="например: кардиолог, УЗИ, общий анализ крови…" />
        <button className="btn primary sb-btn" type="submit">Искать</button>
      </form>
      <div className="muted" style={{ fontSize: 12.5, marginTop: 9 }}>
        Полнотекстовый поиск с морфологией — находит словоформы и устойчив к опечаткам.
      </div>

      <div className="chips" style={{ marginTop: 18 }}>
        <span className="muted" style={{ fontSize: 12.5, alignSelf: "center" }}>Популярное:</span>
        {POPULAR.map((p) => <button key={p} className="chip" onClick={() => run(p)}>{p}</button>)}
      </div>

      {!res && !loading && (
        <p className="muted" style={{ fontSize: 13.5, marginTop: 22 }}>
          Или откройте весь <Link href="/services">справочник услуг</Link> · <Link href="/partners">клиники-партнёры</Link>.
        </p>
      )}

      {loading && <div className="loading" style={{ marginTop: 28 }}>Поиск…</div>}
      {err && <div className="panel pad" style={{ marginTop: 20, color: "var(--oxblood)" }}>{err}</div>}

      {res && !loading && (
        <>
          <div className="row" style={{ marginTop: 26, gap: 14 }}>
            <div className="seg-toggle">
              <button className={scope === "all" ? "on" : ""} onClick={() => setScope("all")}>Всё</button>
              <button className={scope === "services" ? "on" : ""} onClick={() => setScope("services")}>Услуги · {res.services.length}</button>
              <button className={scope === "partners" ? "on" : ""} onClick={() => setScope("partners")}>Партнёры · {res.partners.length}</button>
            </div>
            <div className="spacer" />
            <span className="muted" style={{ fontSize: 13 }}>по запросу «{query}»</span>
          </div>

          {res.services.length === 0 && res.partners.length === 0 && (
            <div className="empty" style={{ marginTop: 18 }}>Ничего не найдено по «{query}». Попробуйте короче или другое слово.</div>
          )}

          {scope !== "partners" && res.services.length > 0 && (
            <>
              <div className="section-title">Услуги · {services.length}</div>
              {cats.length > 1 && (
                <div className="chips" style={{ marginBottom: 12 }}>
                  <button className={`chip ${!cat ? "on" : ""}`} onClick={() => setCat(null)}>Все категории</button>
                  {cats.map((c) => <button key={c} className={`chip ${cat === c ? "on" : ""}`} onClick={() => setCat(c)}>{c}</button>)}
                </div>
              )}
              <div className="panel">
                <table className="table">
                  <thead><tr><th>Услуга</th><th style={{ width: 230 }}>Категория</th><th style={{ width: 120 }}></th></tr></thead>
                  <tbody>
                    {services.map((s) => (
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
            </>
          )}

          {scope !== "services" && res.partners.length > 0 && (
            <>
              <div className="section-title">Партнёры · {partners.length}</div>
              {cities.length > 1 && (
                <div className="chips" style={{ marginBottom: 12 }}>
                  <button className={`chip ${!city ? "on" : ""}`} onClick={() => setCity(null)}>Все города</button>
                  {cities.map((c) => <button key={c} className={`chip ${city === c ? "on" : ""}`} onClick={() => setCity(c)}>{c}</button>)}
                </div>
              )}
              <div className="row" style={{ gap: 10 }}>
                {partners.map((p) => (
                  <Link key={p.id} href={`/partners/${p.id}`} className="panel pad" style={{ minWidth: 200 }}>
                    <b>{p.display_name}</b>
                    <div className="muted" style={{ fontSize: 13 }}>{p.city || "город не указан"}</div>
                  </Link>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}
