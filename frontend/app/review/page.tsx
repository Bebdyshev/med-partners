"use client";
import "../pipeline.css";
import { useState } from "react";
import { api, fmtKzt } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import type { Unmatched, AiCompare } from "@/lib/types";
import { TIER_LABELS } from "@/lib/types";
import { PageHead, Loading, ErrorNote, StatusBadge, Meter } from "@/components/Bits";
import { Glyph } from "@/components/Icon";

const PRESETS = ["0.70", "0.80", "0.90"];
const FMT: Record<string, string> = { xlsx: "Excel", xls: "Excel", docx: "Word", pdf: "PDF", scan_pdf: "скан" };

function sourceLoc(ref: string | null | undefined): string {
  if (!ref) return "";
  const kv: Record<string, string> = {};
  for (const part of ref.split(";")) { const [k, v] = part.split("="); kv[k] = v ?? "1"; }
  const out: string[] = [];
  if (kv.page) out.push(`стр. ${kv.page}`);
  if (kv.sheet) out.push(`лист «${kv.sheet}»`);
  if (kv.table !== undefined && kv.sheet === undefined) out.push(`таблица ${Number(kv.table) + 1}`);
  if (kv.row) out.push(`строка ${kv.row}`);
  if (kv.vision !== undefined) out.push("vision-OCR");
  return out.join(" · ") || ref;
}
function openHref(item: Unmatched): string {
  let href = `/api/documents/${item.document_id}/file`;
  const m = item.source_ref?.match(/page=(\d+)/);
  if (m && (item.file_format || "").includes("pdf")) href += `#page=${m[1]}`;
  return href;
}

function FragmentPreview({ item }: { item: Unmatched }) {
  const { data, loading } = useFetch(() => api.documentPreview(item.document_id!, item.source_ref || ""), [item.item_id]);
  const ok = data?.kind === "table" && data.rows && data.rows.length > 0;
  return (
    <div className="rv-frag">
      <div className="rv-frag-h"><Glyph.table size={14} /> {FMT[item.file_format || ""] || item.file_format} · {data?.label || sourceLoc(item.source_ref) || "фрагмент"}</div>
      {loading && <div className="rv-frag-note">Загрузка фрагмента…</div>}
      {ok && (
        <div className="rv-fragtbl-wrap">
          <table className="rv-fragtbl">
            <tbody>
              {data!.rows!.map((r) => (
                <tr key={r.n} className={r.n === data!.target ? "rv-fragtarget" : ""}>
                  <td className="rv-fragn">{r.n}</td>
                  {r.cells.map((c, ci) => <td key={ci}>{c}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!loading && !ok && (
        <div className="rv-frag-row">
          <div className="rv-frag-name">{item.raw_name}</div>
          {item.raw_code && <div className="rv-frag-code">код {item.raw_code}</div>}
          {item.tiers?.length > 0 && (
            <div className="rv-frag-prices">
              {item.tiers.map((t, j) => <span className="badge ink" key={j}>{TIER_LABELS[t.tier_type] ?? t.tier_type}: {fmtKzt(t.amount_kzt)}</span>)}
            </div>
          )}
        </div>
      )}
      <a className="btn small rv-frag-open" href={openHref(item)} target="_blank" rel="noopener noreferrer"><Glyph.docs size={13} /> Открыть оригинал</a>
    </div>
  );
}

function Preview({ item }: { item: Unmatched }) {
  if (!item.document_id) return <div className="rv-noprev">Источник недоступен — оригинал не сохранён.</div>;
  if ((item.file_format || "").includes("pdf")) {
    const m = item.source_ref?.match(/page=(\d+)/);
    const src = `/api/documents/${item.document_id}/file#page=${m ? m[1] : "1"}&view=FitH`;
    return <iframe className="rv-frame" src={src} title="исходный документ" />;
  }
  return <FragmentPreview item={item} />;
}

export default function ReviewPage() {
  const { data, error, loading, reload } = useFetch(() => api.unmatched(50), []);
  const [done, setDone] = useState<Record<string, string>>({});
  const [idx, setIdx] = useState(0);
  const [busy, setBusy] = useState(false);
  const [ai, setAi] = useState<Record<string, AiCompare | "loading" | "error">>({});

  const pending = (data || []).filter((i) => !done[i.item_id]);
  const index = Math.min(idx, Math.max(0, pending.length - 1));
  const item = pending[index];
  const doneCount = Object.keys(done).length;

  async function confirmMatch(serviceId: string, label: string) {
    if (!item) return;
    setBusy(true);
    try {
      await api.match({ item_id: item.item_id, service_id: serviceId, decided_by: "operator" });
      setDone((d) => ({ ...d, [item.item_id]: label }));
    } catch (e) { alert("Ошибка: " + (e as Error).message); } finally { setBusy(false); }
  }
  async function runAi() {
    if (!item) return;
    const id = item.item_id;
    setAi((a) => ({ ...a, [id]: "loading" }));
    try {
      const r = await api.aiCompare(id);
      setAi((a) => ({ ...a, [id]: r }));
    } catch {
      setAi((a) => ({ ...a, [id]: "error" }));
    }
  }

  // bulk accept (secondary)
  const [thr, setThr] = useState("0.80");
  const [eligible, setEligible] = useState<number | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  async function preview() { setEligible((await api.bulkAccept(parseFloat(thr), true)).eligible); }
  async function applyBulk() {
    if (!window.confirm(`Принять верх очереди со скором ≥ ${thr}? Массовая операция.`)) return;
    setBulkBusy(true);
    try { const r = await api.bulkAccept(parseFloat(thr), false); window.alert(`Принято: ${r.accepted}`); setEligible(null); reload(); }
    catch (e) { window.alert("Ошибка: " + (e as Error).message); } finally { setBulkBusy(false); }
  }

  const aiRes = item ? ai[item.item_id] : undefined;

  return (
    <>
      <PageHead eyebrow="Контроль качества" title="Очередь верификации">
        <button className="btn small" onClick={reload}>Обновить</button>
      </PageHead>

      <details className="rv-bulk">
        <summary>Массовое принятие по порогу</summary>
        <div className="pipe-thr">
          <span className="lab">Принять подсказки со скором ≥</span>
          <input className="input pipe-thr-input" value={thr} onChange={(e) => { setThr(e.target.value); setEligible(null); }} />
          <div className="pipe-presets">
            {PRESETS.map((p) => <button key={p} className={`pipe-preset ${thr === p ? "on" : ""}`} onClick={() => { setThr(p); setEligible(null); }}>{p}</button>)}
          </div>
          <button className="btn small" onClick={preview}>Сколько?</button>
          {eligible !== null && <span className="badge ink">{eligible} позиций</span>}
          <div className="spacer" />
          <button className="btn small primary" disabled={bulkBusy} onClick={applyBulk}>{bulkBusy ? "Принимаю…" : "Принять верх очереди"}</button>
        </div>
      </details>

      {loading && <Loading />}
      {error && <ErrorNote error={error} />}

      {data && pending.length === 0 && (
        <div className="pipe-clear">
          <span className="ic"><Glyph.shield size={26} /></span>
          <div className="t">Очередь пуста</div>
          <div className="s">Все позиции сопоставлены{doneCount > 0 ? ` (в этой сессии — ${doneCount})` : ""}. Новые появятся после загрузки следующего прайс-листа.</div>
        </div>
      )}

      {item && (
        <>
          <div className="rv-nav">
            <button className="btn small" disabled={index <= 0} onClick={() => setIdx(index - 1)}><span style={{ display: "inline-flex", transform: "scaleX(-1)" }}><Glyph.arrow size={13} /></span> Назад</button>
            <span className="rv-count">Позиция <b>{index + 1}</b> из {pending.length}{doneCount > 0 ? ` · сделано ${doneCount}` : ""}</span>
            <button className="btn small" disabled={index >= pending.length - 1} onClick={() => setIdx(index + 1)}>Вперёд <Glyph.arrow size={13} /></button>
          </div>

          <div className="rv-split">
            {/* LEFT — source document preview */}
            <div className="rv-left"><Preview item={item} /></div>

            {/* RIGHT — extracted data + AI verdict + candidates */}
            <div className="rv-right">
              {item.document_id && (
                <div className="pipe-src">
                  <span className="pipe-src-fmt">{FMT[item.file_format || ""] || item.file_format}</span>
                  <span className="pipe-src-file" title={item.source_filename || ""}>{item.partner_name ? `${item.partner_name} · ` : ""}{item.source_filename}</span>
                  {item.year && <span className="pipe-src-loc">{item.year}</span>}
                  {sourceLoc(item.source_ref) && <span className="pipe-src-loc">{sourceLoc(item.source_ref)}</span>}
                  <span className="spacer" />
                  <a className="btn small" href={openHref(item)} target="_blank" rel="noopener noreferrer"><Glyph.docs size={13} /> Открыть</a>
                </div>
              )}

              <div className="rv-extr">
                <div className="pipe-q-cat">{item.raw_category || "без категории"}{item.raw_code ? ` · код ${item.raw_code}` : ""}</div>
                <div className="pipe-q-raw">{item.raw_name}</div>
                <div className="pipe-q-badges">
                  <StatusBadge status={item.match_status} />
                  {item.match_score != null && <span className="badge">скор {item.match_score.toFixed(2)}</span>}
                  {item.extraction_method && <span className="badge mono">{item.extraction_method}</span>}
                  {item.tiers?.map((t, j) => <span className="badge ink" key={j}>{TIER_LABELS[t.tier_type] ?? t.tier_type}: {fmtKzt(t.amount_kzt)}</span>)}
                </div>
              </div>

              <div className="rv-ai">
                <button className="btn primary rv-ai-btn" disabled={aiRes === "loading"} onClick={runAi}>
                  <Glyph.reconcile size={15} /> {aiRes === "loading" ? "ИИ анализирует…" : "ИИ сравнение со справочником"}
                </button>
                {aiRes && aiRes !== "loading" && aiRes !== "error" && (
                  <div className={`rv-verdict ${aiRes.best ? "ok" : "none"}`}>
                    {aiRes.best ? (
                      <>
                        <div className="rv-v-h"><Glyph.check size={14} /> ИИ рекомендует · уверенность {(aiRes.confidence * 100).toFixed(0)}%</div>
                        <div className="rv-v-name">{aiRes.best.canonical_name}</div>
                        {aiRes.reason && <div className="rv-v-reason">{aiRes.reason}</div>}
                        <button className="btn small primary" disabled={busy} onClick={() => confirmMatch(aiRes.best!.service_id, aiRes.best!.canonical_name)}>
                          <Glyph.check size={13} /> Подтвердить рекомендацию ИИ
                        </button>
                      </>
                    ) : (
                      <>
                        <div className="rv-v-h rv-v-none"><Glyph.review size={14} /> ИИ не нашёл подходящей услуги</div>
                        {aiRes.reason && <div className="rv-v-reason">{aiRes.reason}</div>}
                      </>
                    )}
                  </div>
                )}
                {aiRes === "error" && <div className="rv-verdict none"><div className="rv-v-h rv-v-none">ИИ-сравнение недоступно (нет ключа OpenAI или ошибка).</div></div>}
              </div>

              <div className="pipe-sugg-head">Кандидаты справочника</div>
              {item.suggestions.length === 0 ? (
                <div className="pipe-sugg"><span className="none">Кандидатов нет — позицию можно завести в справочник как новую услугу (POST /match).</span></div>
              ) : (
                <div className="pipe-sugg-list">
                  {item.suggestions.map((s, si) => {
                    const aiPick = aiRes && aiRes !== "loading" && aiRes !== "error" && aiRes.best?.service_id === s.service_id;
                    return (
                      <div key={s.service_id} className={`pipe-sugg ${si === 0 ? "best" : ""} ${aiPick ? "rv-aipick" : ""}`}>
                        <Meter score={s.score} />
                        <div className="canon">
                          <div className="rv-tags">
                            {si === 0 && <span className="tag">топ по эмбеддингу</span>}
                            {aiPick && <span className="tag rv-aitag">выбор ИИ</span>}
                          </div>
                          <div className="nm">{s.canonical_name}</div>
                        </div>
                        <button className={`btn small ${si === 0 || aiPick ? "primary" : ""}`} disabled={busy} onClick={() => confirmMatch(s.service_id, s.canonical_name)}>
                          <Glyph.check size={13} /> Подтвердить
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </>
  );
}
