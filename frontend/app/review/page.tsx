"use client";
import "../pipeline.css";
import { useState } from "react";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import type { Unmatched } from "@/lib/types";
import { PageHead, Loading, ErrorNote, StatusBadge, Meter } from "@/components/Bits";
import { Reveal } from "@/components/Motion";
import { Glyph } from "@/components/Icon";

const PRESETS = ["0.70", "0.80", "0.90"];

function band(score: number): { color: string; text: string } {
  if (score >= 0.85) return { color: "var(--ok)", text: "Верх очереди — почти всегда верно; безопасно принимать массово." };
  if (score >= 0.70) return { color: "var(--amber)", text: "Середина — большинство верно, но встречаются ошибки. Просмотрите выборочно." };
  return { color: "var(--oxblood)", text: "Низ — много неточностей. Лучше разбирать вручную, по одной позиции." };
}

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

  function setThreshold(v: string) { setThr(v); setEligible(null); }

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

  const b = band(parseFloat(thr) || 0);
  const doneCount = Object.keys(done).length;

  return (
    <>
      <PageHead eyebrow="Контроль качества" title="Очередь ручной разметки">
        <button className="btn small" onClick={reload}>Обновить</button>
      </PageHead>

      <p className="pipe-lede">
        Здесь оператор замыкает контур: позиции, которые система не сопоставила автоматически, получают
        ранжированные подсказки из справочника. Подтверждение <b>одной кнопкой</b> сохраняется как синоним —
        и в следующий раз машина справится сама.
      </p>

      <Reveal dir="up">
        <div className="panel pad pipe-rv-bulk" style={{ marginBottom: 22 }}>
          <div className="hd"><span className="t">Массовое принятие по порогу</span><span className="sp" /></div>
          <div className="pipe-thr">
            <span className="lab">Принять подсказки со скором ≥</span>
            <input
              className="input pipe-thr-input"
              value={thr}
              onChange={(e) => setThreshold(e.target.value)}
            />
            <div className="pipe-presets">
              {PRESETS.map((p) => (
                <button key={p} className={`pipe-preset ${thr === p ? "on" : ""}`} onClick={() => setThreshold(p)}>{p}</button>
              ))}
            </div>
            <button className="btn small" onClick={preview}>Сколько?</button>
            {eligible !== null && <span className="badge ink">{eligible} позиций</span>}
            <div className="spacer" />
            <button className="btn small primary" disabled={bulkBusy} onClick={applyBulk}>
              {bulkBusy ? "Принимаю…" : "Принять верх очереди"}
            </button>
          </div>
          <div className="pipe-band">
            <span className="dot" style={{ background: b.color }} />
            {b.text}
          </div>
        </div>
      </Reveal>

      {loading && <Loading />}
      {error && <ErrorNote error={error} />}

      {data && pending.length === 0 && (
        <div className="pipe-clear">
          <span className="ic"><Glyph.shield size={26} /></span>
          <div className="t">Очередь пуста</div>
          <div className="s">Все позиции сопоставлены. Новые появятся здесь после загрузки следующего прайс-листа.</div>
        </div>
      )}

      <div style={{ display: "grid", gap: 14 }}>
        {pending.map((item, idx) => (
          <Reveal dir="up" delay={Math.min(idx, 6) * 50} key={item.item_id}>
            <div className="panel pad pipe-q">
              <div className="pipe-q-top">
                <div style={{ minWidth: 0 }}>
                  <div className="pipe-q-cat">{item.raw_category || "без категории"}</div>
                  <div className="pipe-q-raw">{item.raw_name}</div>
                  <div className="pipe-q-badges">
                    <StatusBadge status={item.match_status} />
                    {item.match_score != null && (
                      <span className="badge">скор {item.match_score.toFixed(2)}</span>
                    )}
                    {item.extraction_method && <span className="badge mono">{item.extraction_method}</span>}
                  </div>
                </div>
              </div>

              <div className="pipe-sugg-head">Подсказки справочника</div>
              {item.suggestions.length === 0 ? (
                <div className="pipe-sugg"><span className="none">Кандидатов нет — позицию можно завести в справочник как новую услугу (через&nbsp;API&nbsp;/&nbsp;POST&nbsp;/match).</span></div>
              ) : (
                <div className="pipe-sugg-list">
                  {item.suggestions.map((s, si) => (
                    <div key={s.service_id} className={`pipe-sugg ${si === 0 ? "best" : ""}`}>
                      <Meter score={s.score} />
                      <div className="canon">
                        {si === 0 && <div className="tag">лучшее совпадение</div>}
                        <div className="nm">{s.canonical_name}</div>
                      </div>
                      <button
                        className={`btn small ${si === 0 ? "primary" : ""}`}
                        disabled={busy === item.item_id}
                        onClick={() => confirmMatch(item, s.service_id, s.canonical_name)}
                      >
                        <Glyph.check size={13} /> Подтвердить
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Reveal>
        ))}
      </div>

      {doneCount > 0 && (
        <>
          <div className="section-title">Сопоставлено в этой сессии · {doneCount}</div>
          <div className="panel pad pipe-session">
            {Object.entries(done).map(([id, label]) => (
              <Reveal dir="left" className="row2" key={id}>
                <span className="chk"><Glyph.check size={12} /></span>
                <span className="arr"><Glyph.arrow size={14} /></span>
                <span className="lbl">{label}</span>
              </Reveal>
            ))}
          </div>
        </>
      )}
    </>
  );
}
