"use client";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { PageHead, Loading, ErrorNote } from "@/components/Bits";
import { Glyph } from "@/components/Icon";
import { Reveal } from "@/components/Motion";
import "@/app/discovery.css";

const fmt = (n: number) => n.toLocaleString("ru-RU");
const FMT: Record<string, string> = { xlsx: "Excel", xls: "Excel", docx: "Word", pdf: "PDF", scan_pdf: "скан" };
type SortKey = "items" | "auto" | "fresh" | "name";
const SORTS: [SortKey, string][] = [
  ["items", "по объёму"], ["auto", "по сопоставлению"], ["fresh", "по свежести"], ["name", "по имени"],
];

export default function PartnersPage() {
  const { data, error, loading } = useFetch(() => api.dashboardPartners(), []);
  const [sort, setSort] = useState<SortKey>("items");
  const t = data?.totals;

  const partners = (data?.partners ?? []).slice().sort((a, b) => {
    if (sort === "items") return b.items - a.items;
    if (sort === "auto") return b.auto_pct - a.auto_pct;
    if (sort === "fresh") return (b.latest_year ?? 0) - (a.latest_year ?? 0);
    return a.display_name.localeCompare(b.display_name, "ru");
  });

  return (
    <>
      <PageHead eyebrow="Партнёры" title="Клиники-партнёры">
        {t && <span className="muted" style={{ fontSize: 13, fontFamily: "var(--mono)" }}>{t.partners} клиник · {t.active} активных</span>}
      </PageHead>

      {loading && <Loading />}
      {error && <ErrorNote error={error} />}

      {data && t && (
        <>
          <div className="disc-pstrip">
            <div className="disc-pk"><span className="v">{fmt(t.partners)}</span><span className="l">клиник в реестре</span></div>
            <div className="disc-pk"><span className="v">{fmt(t.with_pricelist)}</span><span className="l">с прайс-листом</span></div>
            <div className="disc-pk"><span className="v">{fmt(t.items)}</span><span className="l">позиций всего</span></div>
            <div className="disc-pk"><span className="v">{t.avg_auto_pct}<span className="u">%</span></span><span className="l">в среднем сопоставлено</span></div>
          </div>

          <div className="disc-cmp-head">
            <div className="disc-cmp-title">Клиники</div>
            <div className="seg-toggle">
              {SORTS.map(([k, lbl]) => (
                <button key={k} className={sort === k ? "on" : ""} onClick={() => setSort(k)}>{lbl}</button>
              ))}
            </div>
          </div>

          {partners.length === 0 ? (
            <div className="empty">Партнёров пока нет</div>
          ) : (
            <Reveal dir="up">
              <div className="panel">
                <table className="svc-table ptbl">
                  <thead>
                    <tr>
                      <th className="r">#</th>
                      <th>Клиника</th>
                      <th>Город</th>
                      <th className="r">Позиций</th>
                      <th>Сопоставлено</th>
                      <th>Прайс</th>
                      <th aria-label="open" />
                    </tr>
                  </thead>
                  <tbody>
                    {partners.map((p, i) => (
                      <tr key={p.id} className={p.is_active ? "" : "ptbl-dim"}>
                        <td className="r svc-rank">{String(i + 1).padStart(2, "0")}</td>
                        <td className="svc-cl">
                          <Link href={`/partners/${p.id}?name=${encodeURIComponent(p.display_name)}`}>{p.display_name}</Link>
                          <span className="ptbl-code">{p.code}</span>
                          {!p.is_active && <span className="badge">архив</span>}
                          {p.legal_name && <div className="svc-city">{p.legal_name}</div>}
                        </td>
                        <td className="ptbl-city">{p.city || "—"}</td>
                        <td className="r svc-year2">{fmt(p.items)}</td>
                        <td className="ptbl-cov">
                          {p.items > 0 ? (
                            <>
                              <span className="ptbl-pct" style={{ color: p.auto_pct >= 60 ? "var(--chart-auto)" : "var(--amber)" }}>{p.auto_pct}%</span>
                              <div className="disc-pm-bar"><i style={{ width: `${Math.min(100, p.auto_pct)}%` }} /></div>
                            </>
                          ) : <span className="muted" style={{ fontSize: 12.5 }}>нет прайса</span>}
                        </td>
                        <td className="ptbl-price">
                          {p.latest_year && <span className="svc-year2">{p.latest_year}</span>}
                          {p.formats.length > 0 && (
                            <span className="ptbl-fmts">{p.formats.map((f) => <span className="disc-pm-fmt" key={f}>{FMT[f] || f}</span>)}</span>
                          )}
                        </td>
                        <td className="r ptbl-go"><Link href={`/partners/${p.id}?name=${encodeURIComponent(p.display_name)}`} aria-label="Открыть клинику"><Glyph.arrow size={15} /></Link></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Reveal>
          )}
        </>
      )}
    </>
  );
}
