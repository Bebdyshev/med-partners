"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import type { Unmatched } from "@/lib/types";
import { PageHead, Loading, ErrorNote, StatusBadge } from "@/components/Bits";
import { Glyph } from "@/components/Icon";

export default function ReviewPage() {
  const { data, error, loading, reload } = useFetch(() => api.unmatched(40), []);
  const [done, setDone] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  async function confirm(item: Unmatched, serviceId: string, label: string) {
    setBusy(item.item_id);
    try {
      await api.match({ item_id: item.item_id, service_id: serviceId, decided_by: "operator" });
      setDone((d) => ({ ...d, [item.item_id]: label }));
    } catch (e) {
      alert("Ошибка: " + (e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const pending = (data || []).filter((i) => !done[i.item_id]);

  return (
    <>
      <PageHead eyebrow="06 · Верификация" title="Очередь ручной разметки">
        <button className="btn small" onClick={reload}>Обновить</button>
      </PageHead>

      <p className="muted" style={{ marginTop: -14, marginBottom: 22, fontSize: 13.5, maxWidth: "62ch" }}>
        Позиции, которые система не сопоставила автоматически. Для каждой — ранжированные подсказки из справочника.
        Оператор подтверждает одной кнопкой; выбор сохраняется как синоним и учит систему.
      </p>

      {loading && <Loading />}
      {error && <ErrorNote error={error} />}

      {data && pending.length === 0 && (
        <div className="empty">Очередь пуста — все позиции сопоставлены. 🗸</div>
      )}

      <div style={{ display: "grid", gap: 14 }}>
        {pending.map((item) => (
          <div key={item.item_id} className="panel pad">
            <div className="between" style={{ alignItems: "flex-start" }}>
              <div>
                <div className="upper muted">{item.raw_category || "без категории"}</div>
                <div style={{ fontSize: 17, fontFamily: "var(--font-display)", marginTop: 3 }}>{item.raw_name}</div>
                <div className="row" style={{ gap: 8, marginTop: 8 }}>
                  <StatusBadge status={item.match_status} />
                  {item.match_score != null && (
                    <span className="badge">скор {item.match_score.toFixed(2)}</span>
                  )}
                  {item.extraction_method && <span className="badge mono">{item.extraction_method}</span>}
                </div>
              </div>
            </div>

            <div className="section-title" style={{ marginTop: 16, marginBottom: 10 }}>Подсказки справочника</div>
            {item.suggestions.length === 0 ? (
              <div className="muted" style={{ fontSize: 13 }}>Кандидатов нет — можно создать новую услугу в справочнике (через API/POST&nbsp;/match).</div>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {item.suggestions.map((s) => (
                  <div key={s.service_id} className="between" style={{ borderBottom: "1px dotted var(--rule)", paddingBottom: 8 }}>
                    <div className="row" style={{ gap: 12 }}>
                      <span className="num" style={{ width: 46, color: scoreColor(s.score) }}>{s.score.toFixed(2)}</span>
                      <span>{s.canonical_name}</span>
                    </div>
                    <button
                      className="btn small primary"
                      disabled={busy === item.item_id}
                      onClick={() => confirm(item, s.service_id, s.canonical_name)}
                    >
                      <span className="row" style={{ gap: 6 }}><Glyph.review size={13} /> Подтвердить</span>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {Object.keys(done).length > 0 && (
        <>
          <div className="section-title">Сопоставлено в этой сессии · {Object.keys(done).length}</div>
          <div className="panel pad" style={{ display: "grid", gap: 6 }}>
            {Object.entries(done).map(([id, label]) => (
              <div key={id} className="row" style={{ gap: 10, fontSize: 13 }}>
                <span className="badge green">✓</span> <span className="muted">→</span> {label}
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}

function scoreColor(s: number): string {
  if (s >= 0.85) return "var(--accent)";
  if (s >= 0.6) return "var(--amber)";
  return "var(--oxblood)";
}
