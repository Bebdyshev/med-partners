"use client";
import { useEffect, useRef, useState } from "react";
import { api, fmtKzt } from "@/lib/api";
import type { DocumentItem, ProgressEvent } from "@/lib/types";
import { Glyph } from "./Icon";
import { StatusBadge } from "./Bits";
import { Counter } from "./Motion";

const STAGES = [
  { lbl: "Чтение файла", det: "формат · дедуп по хэшу" },
  { lbl: "Извлечение и OCR", det: "таблицы · текст · скан" },
  { lbl: "Разбор позиций и цен", det: "строки · тарифы · → ₸" },
  { lbl: "Нормализация к справочнику", det: "код-в-код, затем семантика" },
  { lbl: "Валидация и версии", det: "8 правил · история цен" },
];

const METHOD_RU: Record<string, string> = {
  table: "таблица", ocr: "OCR", words: "текст", lines: "строки", text: "текст", line_items: "строки",
  pdf_text: "PDF · текст", pdf_ocr: "PDF · OCR", pdf_table: "PDF · таблица", xlsx: "Excel", docx: "Word", xls: "Excel",
};

// cosmetic skeleton rows shown while reading, before the first page image arrives
const TROWS = [
  { w: 72, st: "hi" }, { w: 54, st: "hi" }, { w: 64, st: "mid" },
  { w: 46, st: "hi" }, { w: 60, st: "lo" }, { w: 50, st: "mid" },
];

type Tally = { done: number; total: number; auto: number; review: number; unmatched: number };
type Result =
  | { kind: "done"; items: number; methods: [string, number][]; status: string; docId: string; preview: DocumentItem[]; auto: number; review: number; unmatched: number; fromCache?: boolean }
  | { kind: "error"; msg: string };

function MatchMark({ status }: { status: string }) {
  if (status === "auto") return <span className="pp-mk auto"><Glyph.check size={12} /></span>;
  if (status === "review") return <span className="pp-mk review" />;
  return <span className="pp-mk none">?</span>;
}

export default function ParseProgress({
  file,
  onComplete,
  onClose,
}: {
  file: File;
  onComplete: () => void;
  onClose: () => void;
}) {
  const [stage, setStage] = useState(0);
  const [pct, setPct] = useState(2);
  const [pctTarget, setPctTarget] = useState(2);
  const [scan, setScan] = useState<{ page: number; total: number } | null>(null);
  const [recognized, setRecognized] = useState(0);
  const [parseProg, setParseProg] = useState<{ done: number; total: number } | null>(null);
  const [tally, setTally] = useState<Tally | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const docIdRef = useRef<string>("");
  const settledRef = useRef(false);

  // smooth percentage readout — eases toward target so the number climbs like an instrument
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      setPct((p) => {
        const d = pctTarget - p;
        if (Math.abs(d) < 0.4) return pctTarget;
        raf = requestAnimationFrame(tick);
        return p + d * 0.1;
      });
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [pctTarget]);

  useEffect(() => {
    const ctrl = new AbortController();
    let alive = true;

    function settle(r: Result) {
      settledRef.current = true;
      if (alive) setResult(r);
    }

    function handle(ev: ProgressEvent) {
      if (!alive) return;
      switch (ev.stage) {
        case "read":
          setStage(0); setPctTarget(8); break;
        case "extract":
          setStage(1); setPctTarget(14);
          if (ev.page_total) setScan({ page: 0, total: ev.page_total });
          break;
        case "ocr":
          setStage(1); setScan({ page: ev.page, total: ev.page_total });
          setPctTarget(14 + (ev.page / Math.max(1, ev.page_total)) * 34);
          break;
        case "ocr_done":
          setRecognized((r) => r + ev.rows); break;
        case "extract_done":
          setStage(2); setPctTarget(52); setScan(null);
          setParseProg({ done: 0, total: ev.rows });
          break;
        case "parse":
          setStage(2);
          setParseProg({ done: ev.done, total: ev.total });
          setPctTarget(52 + (ev.done / Math.max(1, ev.total)) * 12);
          break;
        case "normalize":
          setStage(3);
          setTally({ done: ev.done, total: ev.total, auto: ev.auto, review: ev.review, unmatched: ev.unmatched });
          setPctTarget(66 + (ev.done / Math.max(1, ev.total)) * 28);
          break;
        case "validate":
          setStage(4); setPctTarget(96); break;
        case "done": {
          setStage(5); setPctTarget(100); setScan(null);
          const m = Object.entries(ev.methods) as [string, number][];
          const items = m.reduce((a, [, n]) => a + n, 0);
          settle({
            kind: "done", items, methods: m, status: String(ev.summary.status), docId: ev.doc_id,
            preview: ev.preview || [],
            auto: Number(ev.summary.auto) || 0, review: Number(ev.summary.review) || 0, unmatched: Number(ev.summary.unmatched) || 0,
          });
          onComplete();
          break;
        }
        case "error":
          settle({ kind: "error", msg: ev.message }); break;
      }
    }

    async function showExisting(docId: string) {
      setStage(5); setPctTarget(100); setScan(null);
      try {
        const r = await api.documentResult(docId);
        if (!alive) return;
        const m = Object.entries(r.methods) as [string, number][];
        const items = m.reduce((a, [, n]) => a + n, 0) || r.summary.items;
        settle({
          kind: "done", items, methods: m, status: String(r.summary.status), docId,
          preview: r.preview || [], auto: r.summary.auto, review: r.summary.review, unmatched: r.summary.unmatched,
          fromCache: true,
        });
        onComplete();
      } catch (e) {
        settle({ kind: "error", msg: (e as Error).message });
      }
    }

    (async () => {
      let up;
      try {
        // process=false: we drive processing via the stream. dedupe OFF so every upload
        // re-runs and plays the full live pipeline (даже если файл уже был в базе —
        // для демо важно показать весь процесс, а не скипнуть на кэш). The existing-data
        // path below is a safety net for when nothing new is created. The abort signal
        // means a discarded StrictMode double-mount doesn't leave an orphan document.
        up = await api.upload(file, false, false, false, ctrl.signal);
      } catch (e) {
        if (!alive) return; // aborted (StrictMode cleanup) — ignore
        settle({ kind: "error", msg: (e as Error).message }); return;
      }
      if (!alive) return;
      if (!up.created.length) {
        // duplicate (or nothing new) — show what's already stored for this file
        if (up.existing && up.existing.length) { await showExisting(up.existing[0]); }
        else settle({ kind: "error", msg: "файл не создан" });
        return;
      }
      docIdRef.current = up.created[0];
      setStage(0); setPctTarget(8);
      try {
        await api.streamProcess(up.created[0], handle, ctrl.signal);
      } catch (e) {
        if (!settledRef.current) settle({ kind: "error", msg: (e as Error).message });
      }
    })();

    return () => { alive = false; ctrl.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ext = (file.name.split(".").pop() || "").toUpperCase().slice(0, 4);
  const sizeKb = file.size < 1024 * 1024
    ? `${Math.max(1, Math.round(file.size / 1024))} КБ`
    : `${(file.size / 1024 / 1024).toFixed(1)} МБ`;
  const done = pct >= 99.5;
  const showScanner = !result && scan && scan.page > 0;

  return (
    <div className="pipe-pp" role="status" aria-live="polite">
      <div className="pipe-pp-head">
        <div className="pipe-pp-chip">
          <Glyph.docs size={18} />
          <span className="ext">{ext}</span>
        </div>
        <div className="pipe-pp-id">
          <div className="pipe-pp-name">{file.name}</div>
          <div className="pipe-pp-meta">{sizeKb} · разбор прайс-листа</div>
        </div>
        <div className="pipe-pp-pct">
          <b>{Math.round(pct)}%</b>
          <div className="l">{result ? "готово" : "обработка"}</div>
        </div>
      </div>

      <div className={`pipe-pp-bar ${done ? "full" : ""}`}><i style={{ width: `${pct}%` }} /></div>

      <div className={`pp-body ${!result ? "live" : ""}`}>
        <div className="pipe-pp-stages">
          {STAGES.map((s, i) => {
            const cls = i < stage ? "done" : i === stage ? "active" : "";
            return (
              <div className={`pipe-stage ${cls}`} key={s.lbl}>
                <span className="mk">
                  {i < stage ? <Glyph.check size={13} /> : i === stage ? <span className="dot" /> : i + 1}
                </span>
                <div>
                  <div className="lbl">{s.lbl}</div>
                  <div className="det">{s.det}</div>
                </div>
              </div>
            );
          })}
        </div>

        {/* right column — live activity beside the stages */}
        {!result && (
          <div className="pp-side">
            {/* live page scanner — the actual page being read, with a sweeping scan line */}
            {showScanner && (
              <div className="pp-scanner">
                <div className="pp-scan-frame">
                  <img
                    key={scan!.page}
                    src={api.pageImageUrl(docIdRef.current, scan!.page)}
                    alt={`страница ${scan!.page}`}
                    className="pp-scan-img"
                  />
                  <div className="pp-scan-tint" />
                  <div className="pp-scanline" />
                </div>
                <div className="pp-scan-meta">
                  <div className="pp-scan-page">
                    <span className="pp-live" /> Распознавание страницы <b>{scan!.page}</b> из {scan!.total}
                  </div>
                  <div className="pp-scan-rows">распознано <b>{recognized}</b> позиций</div>
                </div>
              </div>
            )}

            {/* reading skeleton — before the first page image (or for non-scan files) */}
            {!showScanner && stage <= 1 && (
              <div className="pipe-pp-ticker">
                <div className="pipe-ticker-cap"><span className="pipe-live" /> Поток извлечения</div>
                <div className="pipe-ticker-rows">
                  {TROWS.map((r, i) => (
                    <div className="pipe-trow" key={i}>
                      <span className="nm shimmer" style={{ width: `${r.w}%` }} />
                      <span className="px shimmer" />
                      <span className={`st ${r.st}`} />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* live parse counter — позиции и цены разбираются */}
            {stage === 2 && parseProg && (
              <div className="pp-meter">
                <div className="pp-meter-head">
                  <span><span className="pp-live" /> Разбор позиций и цен</span>
                  <b>{parseProg.done} <span>из {parseProg.total}</span></b>
                </div>
                <div className="pp-meter-bar"><i style={{ width: `${Math.round((parseProg.done / Math.max(1, parseProg.total)) * 100)}%` }} /></div>
              </div>
            )}

            {/* live normalization tallies — real running counts */}
            {stage >= 3 && tally && (
              <div className="pp-tally">
                <div className="pp-tally-head">
                  <span className="pp-live" /> Нормализовано <b>{tally.done}</b> из {tally.total}
                </div>
                <div className="pp-meter-bar"><i style={{ width: `${Math.round((tally.done / Math.max(1, tally.total)) * 100)}%` }} /></div>
                <div className="pp-tally-cells">
                  <div className="pp-tally-cell auto"><b>{tally.auto}</b><span>авто-сопоставлено</span></div>
                  <div className="pp-tally-cell review"><b>{tally.review}</b><span>на проверку</span></div>
                  <div className="pp-tally-cell none"><b>{tally.unmatched}</b><span>не найдено</span></div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {result?.kind === "done" && (
        <div className="pipe-result">
          <div className="pipe-rcells">
            <div className="pipe-rcell hero">
              <div className="k">Извлечено позиций</div>
              <div className="v"><Counter value={result.items} /></div>
            </div>
            <div className="pipe-rcell">
              <div className="k">Метод извлечения</div>
              <div className="methods">
                {result.methods.length === 0 ? <span className="muted">—</span> : result.methods.map(([m, n]) => (
                  <span className="badge" key={m}>{METHOD_RU[m] || m} · {n}</span>
                ))}
              </div>
            </div>
            <div className="pipe-rcell">
              <div className="k">Статус документа</div>
              <div className="stat"><StatusBadge status={result.status} /></div>
            </div>
          </div>

          {result.preview.length > 0 && (
            <div className="pp-preview">
              <div className="pp-preview-head">
                Первые позиции · <span className="pp-pv-auto">{result.auto} авто</span> · <span className="pp-pv-review">{result.review} проверка</span> · <span className="pp-pv-none">{result.unmatched} не найдено</span>
              </div>
              <div className="pp-preview-rows">
                {result.preview.map((it, i) => (
                  <div className="pp-pv-row" key={i}>
                    <MatchMark status={it.match_status} />
                    <div className="pp-pv-raw" title={it.raw_name}>{it.raw_name}</div>
                    <div className="pp-pv-canon">
                      {it.match_status === "auto" && it.canonical_name
                        ? it.canonical_name
                        : it.match_status === "review"
                          ? <span className="pp-pv-tag review">на проверку{it.match_score != null ? ` · ${it.match_score.toFixed(2)}` : ""}</span>
                          : <span className="pp-pv-tag none">нет в справочнике</span>}
                    </div>
                    <div className="pp-pv-price">{it.amount_kzt ? fmtKzt(it.amount_kzt) : "—"}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className={`pipe-note ${result.fromCache ? "warn" : "ok"}`}>
            <span className="ic">{result.fromCache ? <Glyph.layers size={15} /> : <Glyph.check size={15} />}</span>
            {result.fromCache
              ? "Файл уже был обработан ранее — показаны сохранённые данные из базы."
              : "Готово — документ в реестре."}
          </div>
          <div className="pipe-foot">
            <div className="spacer" />
            <a className="btn small" href="/review"><Glyph.review size={13} /> В очередь верификации</a>
            <button className="btn small primary" onClick={onClose}><Glyph.upload size={13} /> Загрузить ещё</button>
          </div>
        </div>
      )}

      {result?.kind === "error" && (
        <div className="pipe-result">
          <div className="pipe-err">
            <b>Не удалось обработать файл.</b>
            <div className="msg">{result.msg}</div>
          </div>
          <div className="pipe-foot">
            <div className="spacer" />
            <button className="btn small" onClick={onClose}>Закрыть</button>
          </div>
        </div>
      )}
    </div>
  );
}
