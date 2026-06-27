"use client";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { SearchResult } from "@/lib/types";
import { Glyph } from "@/components/Icon";
import { Reveal, Stagger, AmbientField } from "@/components/Motion";
import "@/app/discovery.css";

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
      <section className="disc-hero">
        <AmbientField />
        <Reveal dir="up">
          <div className="disc-hero-eyebrow">Поиск по реестру</div>
          <h1>Одна услуга — <span className="disc-em">десятки клиник</span> и их цены</h1>
          <p className="disc-hero-sub">
            Полнотекстовый поиск с морфологией по нормализованному реестру: словоформы,
            опечатки и сырые названия из прайс-листов сводятся к одной услуге.
          </p>
        </Reveal>

        <Reveal dir="up" delay={80}>
          <div className="disc-searchwrap">
            <form className="searchbar" onSubmit={(e) => { e.preventDefault(); run(); }}>
              <span className="sb-ic"><Glyph.find size={20} /></span>
              <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="например: кардиолог, УЗИ, общий анализ крови…" />
              <button className="btn primary sb-btn" type="submit">Искать</button>
            </form>
            <div className="disc-note"><span className="disc-dot" /> Находит словоформы и устойчив к опечаткам</div>
          </div>
        </Reveal>

        <Reveal dir="up" delay={150}>
          <div className="disc-popular">
            <span className="disc-pop-label">Популярное</span>
            {POPULAR.map((p) => <button key={p} className="chip" onClick={() => run(p)}>{p}</button>)}
          </div>
        </Reveal>
      </section>

      {!res && !loading && !err && (
        <Reveal dir="up" delay={120}>
          <div className="disc-gateways">
            <Link href="/services" className="disc-gateway">
              <span className="disc-gw-ic"><Glyph.registry size={20} /></span>
              <span>
                <span className="disc-gw-t">Справочник услуг</span>
                <span className="disc-gw-s" style={{ display: "block" }}>Весь нормализованный реестр</span>
              </span>
              <span className="disc-gw-arrow"><Glyph.arrow size={16} /></span>
            </Link>
            <Link href="/partners" className="disc-gateway">
              <span className="disc-gw-ic"><Glyph.partners size={20} /></span>
              <span>
                <span className="disc-gw-t">Клиники-партнёры</span>
                <span className="disc-gw-s" style={{ display: "block" }}>Источники прайс-листов</span>
              </span>
              <span className="disc-gw-arrow"><Glyph.arrow size={16} /></span>
            </Link>
          </div>
        </Reveal>
      )}

      {loading && <div className="loading" style={{ marginTop: 30 }}>Поиск…</div>}
      {err && <div className="panel pad" style={{ marginTop: 22, color: "var(--oxblood)" }}>{err}</div>}

      {res && !loading && (
        <>
          <div className="disc-resultbar">
            <div className="seg-toggle">
              <button className={scope === "all" ? "on" : ""} onClick={() => setScope("all")}>Всё</button>
              <button className={scope === "services" ? "on" : ""} onClick={() => setScope("services")}>Услуги · {res.services.length}</button>
              <button className={scope === "partners" ? "on" : ""} onClick={() => setScope("partners")}>Партнёры · {res.partners.length}</button>
            </div>
            <div className="spacer" />
            <span className="disc-forquery">по запросу <span className="disc-q">«{query}»</span></span>
          </div>

          {res.services.length === 0 && res.partners.length === 0 && (
            <div className="empty" style={{ marginTop: 18 }}>Ничего не найдено по «{query}». Попробуйте короче или другое слово.</div>
          )}

          {scope !== "partners" && res.services.length > 0 && (
            <>
              <div className="section-title">Услуги · {services.length}</div>
              {cats.length > 1 && (
                <div className="chips" style={{ marginBottom: 14 }}>
                  <button className={`chip ${!cat ? "on" : ""}`} onClick={() => setCat(null)}>Все категории</button>
                  {cats.map((c) => <button key={c} className={`chip ${cat === c ? "on" : ""}`} onClick={() => setCat(c)}>{c}</button>)}
                </div>
              )}
              <div className="panel">
                <table className="table">
                  <thead><tr><th>Услуга</th><th style={{ width: 230 }}>Категория</th><th style={{ width: 130 }}></th></tr></thead>
                  <tbody>
                    {services.map((s) => (
                      <tr key={s.id}>
                        <td style={{ fontWeight: 500 }}>{s.canonical_name}</td>
                        <td className="muted">{s.category || "—"}</td>
                        <td className="num">
                          <Link href={`/services/${s.id}?name=${encodeURIComponent(s.canonical_name)}`} className="disc-reg-link" style={{ justifyContent: "flex-end" }}>
                            клиники и цены <Glyph.arrow size={14} />
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
                <div className="chips" style={{ marginBottom: 14 }}>
                  <button className={`chip ${!city ? "on" : ""}`} onClick={() => setCity(null)}>Все города</button>
                  {cities.map((c) => <button key={c} className={`chip ${city === c ? "on" : ""}`} onClick={() => setCity(c)}>{c}</button>)}
                </div>
              )}
              <Stagger className="disc-pgrid" step={55}>
                {partners.map((p) => (
                  <Link key={p.id} href={`/partners/${p.id}?name=${encodeURIComponent(p.display_name)}`} className="disc-gateway">
                    <span className="disc-gw-ic"><Glyph.partners size={18} /></span>
                    <span style={{ minWidth: 0 }}>
                      <span className="disc-gw-t" style={{ display: "block" }}>{p.display_name}</span>
                      <span className="disc-gw-s">{p.city || "город не указан"}</span>
                    </span>
                    <span className="disc-gw-arrow"><Glyph.arrow size={15} /></span>
                  </Link>
                ))}
              </Stagger>
            </>
          )}
        </>
      )}
    </>
  );
}
