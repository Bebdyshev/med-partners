"use client";
import { use } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, fmtKzt } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import type { Tier } from "@/lib/types";
import { TIER_LABELS } from "@/lib/types";
import { PageHead, Loading, ErrorNote } from "@/components/Bits";

export const dynamic = "force-dynamic";

function residentPrice(tiers: Tier[]): Tier | undefined {
  return tiers.find((t) => t.tier_type === "resident_kzt") ?? tiers[0];
}

export default function ServiceDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const name = useSearchParams().get("name") || "Услуга справочника";
  const { data, error, loading } = useFetch(() => api.servicePartners(id), [id]);

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <Link href="/services" className="muted" style={{ fontSize: 13 }}>← к справочнику</Link>
      </div>
      <PageHead eyebrow="Услуга · поставщики и цены" title={name} />

      {loading && <Loading />}
      {error && <ErrorNote error={error} />}

      {data && (
        <>
          <div className="row" style={{ marginBottom: 14, gap: 16 }}>
            <span className="badge ink">{data.length} клиник</span>
            {data.length > 0 && (
              <span className="muted" style={{ fontSize: 13 }}>
                цены от {fmtKzt(residentPrice(data[0].tiers)?.amount_kzt ?? 0)} до{" "}
                {fmtKzt(residentPrice(data[data.length - 1].tiers)?.amount_kzt ?? 0)}
              </span>
            )}
          </div>

          {data.length === 0 ? (
            <div className="empty">Пока ни одна клиника не сопоставлена с этой услугой.</div>
          ) : (
            <div className="panel">
              <table className="table">
                <thead>
                  <tr>
                    <th>Клиника</th>
                    <th>Название в прайсе</th>
                    <th>Дата</th>
                    <th className="num">Цена (РК)</th>
                    <th>Тарифы</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((p, i) => {
                    const res = residentPrice(p.tiers);
                    return (
                      <tr key={i}>
                        <td>
                          <Link href={`/partners/${p.partner_id}`}>{p.partner_name}</Link>
                          {p.is_verified && <span className="badge green" style={{ marginLeft: 8 }}>✓ выверено</span>}
                        </td>
                        <td className="muted">{p.raw_name}</td>
                        <td className="num muted">{p.effective_date?.slice(0, 4) ?? "—"}</td>
                        <td className="num" style={{ fontSize: 15 }}>{res ? fmtKzt(res.amount_kzt) : "—"}</td>
                        <td>
                          <div className="row" style={{ gap: 6 }}>
                            {p.tiers.map((t, j) => (
                              <span key={j} className="badge" title={t.label_raw || ""}>
                                {(TIER_LABELS[t.tier_type] ?? t.tier_type)}: {fmtKzt(t.amount_kzt)}
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </>
  );
}
