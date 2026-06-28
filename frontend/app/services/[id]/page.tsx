"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, fmtKzt } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import type { Tier, PartnerPrice } from "@/lib/types";
import { TIER_LABELS } from "@/lib/types";
import { Loading, ErrorNote } from "@/components/Bits";
import { Glyph } from "@/components/Icon";
import { Reveal, Counter } from "@/components/Motion";
import "@/app/discovery.css";

function fmtDuration(min: number): string {
  if (min < 60) return `${min} мин`;
  if (min < 1440) return `${Math.round(min / 60)} ч`;
  return `${Math.round(min / 1440)} сут`;
}

export const dynamic = "force-dynamic";

function residentPrice(tiers: Tier[]): Tier | undefined {
  return tiers.find((t) => t.tier_type === "resident_kzt") ?? tiers[0];
}
function priceNum(p: PartnerPrice): number {
  const t = residentPrice(p.tiers);
  const n = t ? parseFloat(t.amount_kzt) : NaN;
  return Number.isFinite(n) ? n : NaN;
}
const yearOf = (p: PartnerPrice) => (p.effective_date ? p.effective_date.slice(0, 4) : null);
function visitKind(raw: string): "Первичный приём" | "Повторный приём" | null {
  if (/первичн/i.test(raw)) return "Первичный приём";
  if (/повторн/i.test(raw)) return "Повторный приём";
  return null;
}
const finite = (xs: number[]) => xs.filter((n) => Number.isFinite(n));

type Reco = { kind: "good" | "warn" | "info"; text: string };

export default function ServiceDetail({ params }: { params: { id: string } }) {
  const { id } = params;
  const name = useSearchParams().get("name") || "Услуга справочника";
  const { data, error, loading } = useFetch(() => api.servicePartners(id), [id]);
  const { data: desc } = useFetch(() => api.serviceDescription(id), [id]);

  const rows = (data ?? []).slice().sort((a, b) => (priceNum(a) || Infinity) - (priceNum(b) || Infinity));
  const nums = finite(rows.map(priceNum));
  const min = nums.length ? Math.min(...nums) : 0;
  const max = nums.length ? Math.max(...nums) : 0;
  const ratio = min > 0 ? max / min : 0;
  const median = nums.length ? [...nums].sort((a, b) => a - b)[Math.floor(nums.length / 2)] : 0;

  // year comparison
  const byYear = new Map<string, number[]>();
  for (const p of rows) {
    const y = yearOf(p);
    const n = priceNum(p);
    if (!y || !Number.isFinite(n)) continue;
    if (!byYear.has(y)) byYear.set(y, []);
    byYear.get(y)!.push(n);
  }
  const years = [...byYear.entries()].sort((a, b) => a[0].localeCompare(b[0]));

  // first / repeat visit split (consultation services)
  const hasP = rows.some((p) => visitKind(p.raw_name) === "Первичный приём");
  const hasR = rows.some((p) => visitKind(p.raw_name) === "Повторный приём");
  const split = hasP && hasR;
  const groups: [string | null, PartnerPrice[]][] = split
    ? ([
        ["Первичный приём", rows.filter((p) => visitKind(p.raw_name) === "Первичный приём")],
        ["Повторный приём", rows.filter((p) => visitKind(p.raw_name) === "Повторный приём")],
        ["Без уточнения", rows.filter((p) => !visitKind(p.raw_name))],
      ] as [string, PartnerPrice[]][]).filter(([, g]) => g.length)
    : [[null, rows]];

  // smart recommendations
  const recos: Reco[] = [];
  if (rows.length) {
    const cheapest = rows[0];
    const cn = priceNum(cheapest);
    const savePct = max > min ? Math.round((1 - min / max) * 100) : 0;
    recos.push({
      kind: "good",
      text: `Лучшая цена — ${cheapest.partner_name}: ${fmtKzt(cn)}${savePct >= 5 ? ` — на ${savePct}% дешевле самой дорогой (${fmtKzt(max)})` : ""}.`,
    });
    const maxYear = years.length ? years[years.length - 1][0] : null;
    const cYear = yearOf(cheapest);
    if (maxYear && cYear && cYear < maxYear) {
      const fresh = rows.find((p) => yearOf(p) === maxYear);
      recos.push({
        kind: "warn",
        text: `У самой дешёвой клиники прайс за ${cYear}; свежее всего — ${fresh?.partner_name} (${maxYear}). Стоит уточнить актуальность цены.`,
      });
    }
    if (cheapest.is_verified) recos.push({ kind: "info", text: "Цена самой дешёвой клиники выверена вручную." });
    recos.push({
      kind: "info",
      text: ratio < 1.05
        ? "Цены на рынке почти не отличаются — выбирайте по удобству."
        : `Разброс цен ×${ratio.toFixed(1)}, медиана ${fmtKzt(median)}.`,
    });
  }

  return (
    <>
      <div className="disc-back"><Link href="/services"><Glyph.arrow size={13} className="disc-flip" /> к справочнику</Link></div>

      <div className="page-head">
        <div>
          <div className="eyebrow">Услуга · кто оказывает и по какой цене</div>
          <h1>{name}</h1>
        </div>
      </div>

      {/* service encyclopedia description */}
      {desc && (
        <Reveal dir="up">
          <div className="svc-desc">
            {desc.found ? (
              <>
                {desc.short && <p className="svc-desc-short">{desc.short}</p>}
                <div className="svc-desc-grid">
                  {desc.what && (
                    <div className="svc-desc-block">
                      <div className="svc-desc-label">Что исследуется</div>
                      <div className="svc-desc-text">{desc.what}</div>
                    </div>
                  )}
                  {desc.why && (
                    <div className="svc-desc-block">
                      <div className="svc-desc-label">Когда назначается</div>
                      <div className="svc-desc-text">{desc.why}</div>
                    </div>
                  )}
                  {desc.prep && (
                    <div className="svc-desc-block">
                      <div className="svc-desc-label">Как подготовиться</div>
                      <div className="svc-desc-text">{desc.prep}</div>
                    </div>
                  )}
                </div>
                <div className="svc-desc-meta">
                  {desc.duration_min != null && <span><Glyph.clock size={12} /> {fmtDuration(desc.duration_min)}</span>}
                  {desc.category && <span>{desc.category}</span>}
                  {desc.icd_code && <span className="mono">МКБ {desc.icd_code}</span>}
                </div>
              </>
            ) : (
              <div className="svc-desc-grid">
                {desc.category && (
                  <div className="svc-desc-block">
                    <div className="svc-desc-label">Категория</div>
                    <div className="svc-desc-text">{desc.category}</div>
                  </div>
                )}
                {desc.icd_code && (
                  <div className="svc-desc-block">
                    <div className="svc-desc-label">Код МКБ</div>
                    <div className="svc-desc-text mono">{desc.icd_code}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        </Reveal>
      )}

      {loading && <Loading />}
      {error && <ErrorNote error={error} />}
      {data && data.length === 0 && <div className="empty">Пока ни одна клиника не сопоставлена с этой услугой.</div>}

      {data && data.length > 0 && (
        <>
          <Reveal dir="up">
            <div className="disc-sum">
              <div className="disc-sum-cell">
                <div className="disc-sum-k">Клиник предлагают</div>
                <div className="disc-sum-v"><Counter value={data.length} duration={1100} /></div>
              </div>
              <div className="disc-sum-cell disc-sum-range">
                <div className="disc-sum-k">Дешевле всего</div>
                <div className="disc-sum-v">{fmtKzt(min)}</div>
              </div>
              <div className="disc-sum-cell disc-sum-range">
                <div className="disc-sum-k">Дороже всего</div>
                <div className="disc-sum-v">{fmtKzt(max)}</div>
              </div>
              <div className="disc-sum-spread">
                <div className="disc-spread-v">{ratio >= 1.05 ? `разброс ×${ratio.toFixed(1)}` : "цены сопоставимы"}</div>
                <div className="disc-spread-k">{max > min ? `разница ${fmtKzt(max - min)} между клиниками` : "одна цена на рынке"}</div>
              </div>
            </div>
          </Reveal>

          {/* smart recommendations */}
          {recos.length > 0 && (
            <Reveal dir="up">
              <div className="svc-recos">
                {recos.map((r, i) => (
                  <div className={`svc-reco ${r.kind}`} key={i}><span className="dot" />{r.text}</div>
                ))}
              </div>
            </Reveal>
          )}

          {/* year comparison */}
          {years.length >= 2 && (
            <>
              <div className="disc-cmp-head">
                <div className="disc-cmp-title">Цены по годам</div>
                <div className="disc-cmp-hint">минимум за год · по датам прайс-листов</div>
              </div>
              <Reveal dir="up">
                <div className="svc-years">
                  {years.map(([y, arr], i) => {
                    const ymin = Math.min(...arr);
                    const prev = i > 0 ? Math.min(...years[i - 1][1]) : null;
                    const trend = prev == null ? "" : ymin > prev ? "↑" : ymin < prev ? "↓" : "=";
                    return (
                      <div className="svc-year" key={y}>
                        <div className="yy">прайс {y}</div>
                        <div className="ym">от {fmtKzt(ymin)}</div>
                        <div className="yn">
                          {arr.length} {arr.length === 1 ? "клиника" : "клиник"}
                          {trend && <span className={`yt ${ymin > (prev ?? 0) ? "up" : ymin < (prev ?? 0) ? "down" : ""}`}>{trend}</span>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Reveal>
            </>
          )}

          {/* comparison tables (split by visit kind when applicable) */}
          {groups.map(([label, g], gi) => {
            const gmin = (() => { const v = finite(g.map(priceNum)); return v.length ? Math.min(...v) : 0; })();
            return (
              <div key={gi}>
                <div className="disc-cmp-head">
                  <div className="disc-cmp-title">{label ? `${label} · ${g.length}` : "Сравнение цен — дешевле сверху"}</div>
                  <div className="disc-cmp-hint">цена для граждан РК · дешевле сверху</div>
                </div>
                <Reveal dir="up">
                  <div className="panel">
                    <table className="svc-table">
                      <thead>
                        <tr>
                          <th className="r">#</th>
                          <th>Клиника</th>
                          <th>Позиция в прайсе</th>
                          <th>Год</th>
                          <th className="r">Цена, ₸</th>
                        </tr>
                      </thead>
                      <tbody>
                        {g.map((p, i) => {
                          const res = residentPrice(p.tiers);
                          const n = priceNum(p);
                          const best = Number.isFinite(n) && n === gmin;
                          const delta = Number.isFinite(n) ? n - gmin : NaN;
                          const w = max > 0 && Number.isFinite(n) ? Math.max(4, (n / max) * 100) : 0;
                          return (
                            <tr className={best ? "svc-best" : ""} key={i}>
                              <td className="r svc-rank">{String(i + 1).padStart(2, "0")}</td>
                              <td className="svc-cl">
                                <Link href={`/partners/${p.partner_id}?name=${encodeURIComponent(p.partner_name)}`}>{p.partner_name}</Link>
                                {best && <span className="svc-bestflag">дешевле всех</span>}
                                {p.is_verified && <span className="disc-verified"><Glyph.check size={10} /> выверено</span>}
                                {p.city && <div className="svc-city">{p.city}</div>}
                              </td>
                              <td className="svc-raw" title={p.raw_name}>
                                {p.raw_name}
                                {p.tiers.length > 1 && (
                                  <div className="svc-tiers">
                                    {p.tiers.map((t, j) => (
                                      <span className="svc-tier" key={j} title={t.label_raw || ""}>
                                        {TIER_LABELS[t.tier_type] ?? t.tier_type}: {fmtKzt(t.amount_kzt)}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </td>
                              <td className="svc-year2">{yearOf(p) ?? "—"}</td>
                              <td className="r svc-price">
                                <div className="svc-pnum">{res ? fmtKzt(res.amount_kzt) : "—"}</div>
                                <div className="svc-pbar"><i style={{ width: `${w}%` }} /></div>
                                <div className="svc-pdelta">{best ? "минимум" : Number.isFinite(delta) && delta > 0 ? `+${fmtKzt(delta)}` : "—"}</div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </Reveal>
              </div>
            );
          })}
        </>
      )}
    </>
  );
}
