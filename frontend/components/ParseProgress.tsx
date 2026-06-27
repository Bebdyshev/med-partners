"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { DocumentRow } from "@/lib/types";
import { Glyph } from "./Icon";
import { StatusBadge } from "./Bits";

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
  const [pct, setPct] = useState(4);
  const [skeleton, setSkeleton] = useState(0);
  const [result, setResult] = useState<Result | null>(null);

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
        setPct(s.pct);
        if (s.i >= 1) setSkeleton((n) => Math.min(5, n + 2));
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
        setPct(100);
        return;
      }

      const methods = Object.entries(doc?.method_summary || {}) as [string, number][];
      const items = methods.reduce((a, [, n]) => a + n, 0);
      setStage(5);
      setPct(100);
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

  return (
    <div className="pp" role="status" aria-live="polite">
      <div className="pp-head">
        <div className="pp-file">
          <Glyph.docs size={18} />
          <span className="ext">{ext}</span>
        </div>
        <div style={{ minWidth: 0 }}>
          <div className="pp-name">{file.name}</div>
          <div className="pp-meta">{sizeKb} · разбор прайс-листа</div>
        </div>
        <div className="pp-pct num">{pct}%</div>
      </div>

      <div className="pp-bar"><i style={{ width: `${pct}%` }} /></div>

      <div className="pp-stages">
        {STAGES.map((s, i) => {
          const cls = i < stage ? "done" : i === stage ? "active" : "";
          return (
            <div className={`pp-stage ${cls}`} key={s.lbl}>
              <span className="mk">
                {i < stage ? <Glyph.check size={13} /> : i === stage ? <span className="pulse" /> : <span style={{ width: 6, height: 6, borderRadius: 50, background: "currentColor" }} />}
              </span>
              <span className="lbl">{s.lbl}</span>
              <span className="det">{s.det}</span>
            </div>
          );
        })}
      </div>

      {/* extraction shimmer — placeholders while rows are being read */}
      {!result && (
        <div className="pp-ticker">
          <div className="cap">Поток извлечения</div>
          <div className="pp-rows">
            {Array.from({ length: skeleton }).map((_, i) => (
              <div className="pp-rowline" key={i}>
                <span className="nm" style={{ height: 9, borderRadius: 4, background: "var(--paper-3)", width: `${70 - i * 8}%` }} />
                <span className="px" style={{ height: 9, width: 54, borderRadius: 4, background: "var(--paper-3)" }} />
                <span className="st" style={{ background: "var(--rule-strong)" }} />
              </div>
            ))}
          </div>
        </div>
      )}

      {result?.kind === "done" && (
        <div className="pp-result">
          <div className="grid">
            <div className="pp-rcell">
              <div className="k">Извлечено позиций</div>
              <div className="v num">{result.items.toLocaleString("ru-RU")}</div>
            </div>
            <div className="pp-rcell">
              <div className="k">Метод извлечения</div>
              <div className="row" style={{ gap: 6, marginTop: 8 }}>
                {result.methods.length === 0 ? <span className="muted">—</span> : result.methods.map(([m, n]) => (
                  <span className="badge" key={m}>{METHOD_RU[m] || m} · {n}</span>
                ))}
              </div>
            </div>
            <div className="pp-rcell">
              <div className="k">Статус документа</div>
              <div style={{ marginTop: 10 }}><StatusBadge status={result.status} /></div>
            </div>
          </div>
          <div className="row">
            <span className="row" style={{ gap: 8, color: "var(--ok)", fontSize: 14 }}>
              <Glyph.check size={16} /> Готово — документ в реестре
            </span>
            <div className="spacer" />
            <a className="btn small" href="/review"><Glyph.review size={13} /> В очередь верификации</a>
            <button className="btn small primary" onClick={onClose}><Glyph.upload size={13} /> Загрузить ещё</button>
          </div>
        </div>
      )}

      {result?.kind === "dup" && (
        <div className="pp-result">
          <span className="row" style={{ gap: 8, color: "var(--amber)", fontSize: 14 }}>
            <Glyph.layers size={16} /> Дубликат — файл уже есть в базе (дедуп по хэшу).
          </span>
          <div className="row">
            <div className="spacer" />
            <button className="btn small primary" onClick={onClose}>Загрузить другой</button>
          </div>
        </div>
      )}

      {result?.kind === "error" && (
        <div className="pp-result">
          <div className="panel pad" style={{ borderColor: "var(--oxblood)", color: "var(--oxblood)", boxShadow: "none" }}>
            <b>Не удалось обработать файл.</b>
            <div className="mono" style={{ fontSize: 12.5, marginTop: 6 }}>{result.msg}</div>
          </div>
          <div className="row">
            <div className="spacer" />
            <button className="btn small" onClick={onClose}>Закрыть</button>
          </div>
        </div>
      )}
    </div>
  );
}
