"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { DocumentRow } from "@/lib/types";
import { Glyph } from "./Icon";
import { StatusBadge } from "./Bits";
import { Counter } from "./Motion";

const STAGES = [
  { lbl: "Чтение файла", det: "формат · дедуп по хэшу" },
  { lbl: "Извлечение", det: "таблицы · текст · OCR" },
  { lbl: "Разбор позиций и цен", det: "строки · тарифы · → ₸" },
  { lbl: "Нормализация к справочнику", det: "код-в-код, затем семантика" },
  { lbl: "Валидация и версии", det: "8 правил · история цен" },
];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

type Result =
  | { kind: "done"; items: number; methods: [string, number][]; status: string; docId: string }
  | { kind: "dup" }
  | { kind: "error"; msg: string };

const METHOD_RU: Record<string, string> = {
  table: "таблица", ocr: "OCR", words: "текст", lines: "строки", text: "текст", line_items: "строки",
  pdf_text: "PDF · текст", pdf_ocr: "PDF · OCR", pdf_table: "PDF · таблица", xlsx: "Excel", docx: "Word", xls: "Excel",
};

// deterministic console-row geometry (purely cosmetic skeleton stream)
const TROWS = [
  { w: 72, st: "hi" }, { w: 54, st: "hi" }, { w: 64, st: "mid" },
  { w: 46, st: "hi" }, { w: 60, st: "lo" }, { w: 50, st: "mid" },
];

export default function ParseProgress({
  file,
  onComplete,
  onClose,
}: {
  file: File;
  onComplete: () => void;
  onClose: () => void;
}) {
  // active stage index; stages with idx < stage are "done", == stage is "active"
  const [stage, setStage] = useState(0);
  const [pctTarget, setPctTarget] = useState(4);
  const [pct, setPct] = useState(4);
  const [skeleton, setSkeleton] = useState(0);
  const [result, setResult] = useState<Result | null>(null);

  // smooth percentage readout — eases the displayed value toward its target,
  // so the number visibly climbs like an instrument rather than jumping.
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      setPct((p) => {
        const d = pctTarget - p;
        if (Math.abs(d) < 0.5) return pctTarget;
        raf = requestAnimationFrame(tick);
        return p + d * 0.09;
      });
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [pctTarget]);

  useEffect(() => {
    let alive = true;
    (async () => {
      const started = performance.now();
      // kick off the REAL work: inline upload + processing, then fetch the parsed doc
      const work = api
        .upload(file, false)
        .then(async (r) => {
          let doc: DocumentRow | null = null;
          if (r.created.length) {
            try { doc = await api.document(r.created[0]); } catch { /* ignore */ }
          }
          return { r, doc };
        });

      // drive the stage sequence while the work runs
      const seq = [
        { i: 0, pct: 14, ms: 520 },
        { i: 1, pct: 40, ms: 820 },
        { i: 2, pct: 64, ms: 820 },
        { i: 3, pct: 84, ms: 760 },
      ];
      for (const s of seq) {
        if (!alive) return;
        setStage(s.i);
        setPctTarget(s.pct);
        if (s.i >= 1) setSkeleton((n) => Math.min(TROWS.length, n + 2));
        await sleep(s.ms);
      }

      let res: { r: Awaited<typeof work>["r"]; doc: DocumentRow | null };
      try {
        res = await work;
      } catch (e) {
        if (alive) setResult({ kind: "error", msg: (e as Error).message });
        return;
      }
      if (!alive) return;

      // hold a minimum so the sequence is legible even on fast files
      const elapsed = performance.now() - started;
      if (elapsed < 2600) await sleep(2600 - elapsed);
      if (!alive) return;

      const { r, doc } = res;
      if (!r.created.length && r.skipped_duplicates) {
        setResult({ kind: "dup" });
        setStage(5);
        setPctTarget(100);
        return;
      }

      const methods = Object.entries(doc?.method_summary || {}) as [string, number][];
      const items = methods.reduce((a, [, n]) => a + n, 0);
      setStage(5);
      setPctTarget(100);
      setResult({
        kind: "done",
        items,
        methods,
        status: doc?.status || "done",
        docId: r.created[0],
      });
      onComplete();
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ext = (file.name.split(".").pop() || "").toUpperCase().slice(0, 4);
  const sizeKb = file.size < 1024 * 1024
    ? `${Math.max(1, Math.round(file.size / 1024))} КБ`
    : `${(file.size / 1024 / 1024).toFixed(1)} МБ`;
  const done = pct >= 99.5;

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

      {/* live extraction console — rows materialising while reading */}
      {!result && (
        <div className="pipe-pp-ticker">
          <div className="pipe-ticker-cap"><span className="pipe-live" /> Поток извлечения</div>
          <div className="pipe-ticker-rows">
            {TROWS.slice(0, skeleton).map((r, i) => (
              <div className="pipe-trow" key={i}>
                <span className="nm shimmer" style={{ width: `${r.w}%` }} />
                <span className="px shimmer" />
                <span className={`st ${r.st}`} />
              </div>
            ))}
          </div>
        </div>
      )}

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
          <div className="pipe-note ok">
            <span className="ic"><Glyph.check size={15} /></span>
            Готово — документ в реестре.
          </div>
          <div className="pipe-foot">
            <div className="spacer" />
            <a className="btn small" href="/review"><Glyph.review size={13} /> В очередь верификации</a>
            <button className="btn small primary" onClick={onClose}><Glyph.upload size={13} /> Загрузить ещё</button>
          </div>
        </div>
      )}

      {result?.kind === "dup" && (
        <div className="pipe-result">
          <div className="pipe-note warn">
            <span className="ic"><Glyph.layers size={15} /></span>
            Дубликат — файл уже есть в базе (дедуп по хэшу).
          </div>
          <div className="pipe-foot">
            <div className="spacer" />
            <button className="btn small primary" onClick={onClose}>Загрузить другой</button>
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
