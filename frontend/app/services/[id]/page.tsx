"use client";
import type { CSSProperties } from "react";
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

export const dynamic = "force-dynamic";

function residentPrice(tiers: Tier[]): Tier | undefined {
  return tiers.find((t) => t.tier_type === "resident_kzt") ?? tiers[0];
}
function priceNum(p: PartnerPrice): number {
  const t = residentPrice(p.tiers);
  const n = t ? parseFloat(t.amount_kzt) : NaN;
  return Number.isFinite(n) ? n : NaN;
}

export default function ServiceDetail({ params }: { params: { id: string } }) {
  const { id } = params;
  const name = useSearchParams().get("name") || "Услуга справочника";
  const { data, error, loading } = useFetch(() => api.servicePartners(id), [id]);

  const rows = data ?? [];
  const nums = rows.map(priceNum);
  const valid = nums.filter((n) => Number.isFinite(n)) as number[];
  const min = valid.length ? Math.min(...valid) : 0;
  const max = valid.length ? Math.max(...valid) : 0;
  const ratio = min > 0 ? max / min : 0;

  return (
    <>
      <div className="disc-back"><Link href="/services"><Glyph.arrow size={13} className="disc-flip" /> к справочнику</Link></div>

      <div className="page-head">
        <div>
          <div className="eyebrow">Услуга · кто оказывает и по какой цене</div>
          <h1>{name}</h1>
        </div>
      </div>

      {loading && <Loading />}
      {error && <ErrorNote error={error} />}

      {data && data.length === 0 && (
        <div className="empty">Пока ни одна клиника не сопоставлена с этой услугой.</div>
      )}

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
                <div className="disc-spread-v">
                  {ratio >= 1.05 ? `разброс ×${ratio.toFixed(1)}` : "цены сопоставимы"}
                </div>
                <div className="disc-spread-k">
                  {max > min ? `разница ${fmtKzt(max - min)} между клиниками` : "одна цена на рынке"}
                </div>
              </div>
            </div>
          </Reveal>

          <div className="disc-cmp-head">
            <div className="disc-cmp-title">Сравнение цен — дешевле сверху</div>
            <div className="disc-cmp-hint">цена для граждан РК · длина полосы = относительно максимума</div>
          </div>

          <div className="disc-cmp">
            {data.map((p, i) => {
              const res = residentPrice(p.tiers);
              const n = nums[i];
              const w = max > 0 && Number.isFinite(n) ? Math.max(0.04, n / max) : 0;
              const best = i === 0;
              const delta = Number.isFinite(n) ? n - min : NaN;
              return (
                <Reveal dir="up" delay={Math.min(i * 55, 600)} key={i}>
                  <div className={`disc-cmprow ${best ? "disc-best" : ""}`}>
                    <div className="disc-cmp-clinic">
                      <div className="disc-cl-rank">{String(i + 1).padStart(2, "0")}</div>
                      <div className="disc-cl-name">
                        <Link href={`/partners/${p.partner_id}?name=${encodeURIComponent(p.partner_name)}`}>{p.partner_name}</Link>
                        {best && <span className="disc-best-flag">ДЕШЕВЛЕ ВСЕХ</span>}
                        {p.is_verified && <span className="disc-verified"><Glyph.check size={10} /> выверено</span>}
                      </div>
                      {p.city && <div className="disc-cl-city">{p.city}</div>}
                    </div>

                    <div className="disc-cmp-mid">
                      <div className="disc-cmp-raw">
                        <span className="disc-raw-q">в прайсе: </span>{p.raw_name}
                      </div>
                      <div className="disc-bar">
                        <i style={{ "--w": w, "--d": `${Math.min(i * 55, 600) + 120}ms` } as CSSProperties} />
                      </div>
                    </div>

                    <div className="disc-cmp-price">
                      <div className="disc-price-v">{res ? fmtKzt(res.amount_kzt) : "—"}</div>
                      <div className="disc-price-delta">
                        {best ? "минимум" : Number.isFinite(delta) && delta > 0 ? `+${fmtKzt(delta)}` : "—"}
                      </div>
                    </div>

                    {p.tiers.length > 0 && (
                      <div className="disc-tiers" style={{ gridColumn: "1 / -1" }}>
                        {p.tiers.map((t, j) => (
                          <span key={j} className="disc-tierbadge" title={t.label_raw || ""}>
                            <span className="disc-tb-k">{TIER_LABELS[t.tier_type] ?? t.tier_type}</span>
                            <span className="disc-tb-v">{fmtKzt(t.amount_kzt)}</span>
                          </span>
                        ))}
                        {p.effective_date && <span className="disc-tierbadge"><span className="disc-tb-k">прайс</span><span className="disc-tb-v">{p.effective_date.slice(0, 4)}</span></span>}
                      </div>
                    )}
                  </div>
                </Reveal>
              );
            })}
          </div>
        </>
      )}
    </>
  );
}
