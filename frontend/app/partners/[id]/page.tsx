"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import type { ServicePrice } from "@/lib/types";
import { PageHead, Loading, ErrorNote, StatusBadge, PriceTiers } from "@/components/Bits";

export const dynamic = "force-dynamic";

export default function PartnerDetail({ params }: { params: { id: string } }) {
  const { id } = params;
  const name = useSearchParams().get("name") || "Прайс-лист клиники";
  const { data, error, loading } = useFetch(() => api.partnerServices(id), [id]);
  const [q, setQ] = useState("");

  const groups = useMemo(() => {
    if (!data) return [];
    const filtered = q
      ? data.filter((d) => d.raw_name.toLowerCase().includes(q.toLowerCase()))
      : data;
    const map = new Map<string, ServicePrice[]>();
    for (const it of filtered) {
      const k = it.category || "Без категории";
      (map.get(k) ?? map.set(k, []).get(k)!).push(it);
    }
    return [...map.entries()];
  }, [data, q]);

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <Link href="/partners" className="muted" style={{ fontSize: 13 }}>← к партнёрам</Link>
      </div>
      <PageHead eyebrow="Партнёр · прайс-лист" title={name}>
        {data && <span className="badge ink">{data.length} позиций</span>}
      </PageHead>

      {loading && <Loading />}
      {error && <ErrorNote error={error} />}

      {data && (
        <>
          <input
            className="input" style={{ maxWidth: 420, marginBottom: 18 }}
            value={q} onChange={(e) => setQ(e.target.value)} placeholder="фильтр по услуге…"
          />
          {groups.map(([cat, items]) => (
            <div key={cat} style={{ marginBottom: 26 }}>
              <div className="section-title" style={{ marginTop: 0 }}>{cat} · {items.length}</div>
              <div className="panel">
                <table className="table">
                  <thead>
                    <tr><th>Услуга в прайсе</th><th style={{ width: 110 }}>Норм.</th><th style={{ width: 260 }}>Тарифы</th></tr>
                  </thead>
                  <tbody>
                    {items.map((it, i) => (
                      <tr key={i}>
                        <td>{it.raw_name}</td>
                        <td><StatusBadge status={it.match_status} /></td>
                        <td><PriceTiers tiers={it.tiers} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
          {groups.length === 0 && <div className="empty">Ничего не найдено</div>}
        </>
      )}
    </>
  );
}
