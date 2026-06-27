"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import type { Unmatched } from "@/lib/types";
import { PageHead, Loading, ErrorNote, StatusBadge, Meter } from "@/components/Bits";
import { Glyph } from "@/components/Icon";

export default function ReviewPage() {
  const { data, error, loading, reload } = useFetch(() => api.unmatched(40), []);
  const [done, setDone] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  async function confirmMatch(item: Unmatched, serviceId: string, label: string) {
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

  // bulk accept
  const [thr, setThr] = useState("0.80");
  const [eligible, setEligible] = useState<number | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  async function preview() {
    setEligible(null);
    const r = await api.bulkAccept(parseFloat(thr), true);
    setEligible(r.eligible);
  }
  async function applyBulk() {
    const score = parseFloat(thr);
    if (!window.confirm(`Принять верх очереди со скором ≥ ${score}? Это массовая операция.`)) return;
    setBulkBusy(true);
    try {
      const r = await api.bulkAccept(score, false);
      window.alert(`Принято: ${r.accepted}`);
      setEligible(null);
      reload();
    } catch (e) {
      window.alert("Ошибка: " + (e as Error).message);
    } finally {
      setBulkBusy(false);
    }
  }

  return (
    <>
      <PageHead eyebrow="Контроль качества" title="Очередь ручной разметки">
        <button className="btn small" onClick={reload}>Обновить</button>
      </PageHead>

      <p className="muted" style={{ marginTop: -14, marginBottom: 22, fontSize: 13.5, maxWidth: "62ch" }}>
        Позиции, которые система не сопоставила автоматически. Для каждой — ранжированные подсказки из справочника.
        Оператор подтверждает одной кнопкой; выбор сохраняется как синоним и учит систему.
      </p>

      <div className="panel pad" style={{ marginBottom: 22 }}>
        <div className="upper muted" style={{ marginBottom: 10 }}>Массовое принятие по порогу</div>
        <div className="row" style={{ gap: 12 }}>
          <span style={{ fontSize: 14 }}>Принять все подсказки со скором ≥</span>
          <input
            className="input" style={{ width: 80, padding: "7px 10px", textAlign: "center" }}
            value={thr} onChange={(e) => { setThr(e.target.value); setEligible(null); }}
          />
          <button className="btn small" onClick={preview}>Сколько?</button>
          {eligible !== null && <span className="badge ink">{eligible} позиций</span>}
          <div className="spacer" />
          <button className="btn small primary" disabled={bulkBusy} onClick={applyBulk}>
            {bulkBusy ? "Принимаю…" : "Принять верх очереди"}
          </button>
        </div>
        <div className="muted" style={{ fontSize: 12, marginTop: 9 }}>
          Верх (≥0.80) почти всегда верный; чем ниже порог, тем больше ошибок. Низ 0.60–0.70 лучше разбирать вручную.
        </div>
      </div>

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
                <div style={{ fontSize: 17, fontWeight: 600, marginTop: 4 }}>{item.raw_name}</div>
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
                  <div key={s.service_id} className="between" style={{ borderBottom: "1px dashed var(--rule)", paddingBottom: 10 }}>
                    <div className="row" style={{ gap: 14 }}>
                      <Meter score={s.score} />
                      <span>{s.canonical_name}</span>
                    </div>
                    <button
                      className="btn small primary"
                      disabled={busy === item.item_id}
                      onClick={() => confirmMatch(item, s.service_id, s.canonical_name)}
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
