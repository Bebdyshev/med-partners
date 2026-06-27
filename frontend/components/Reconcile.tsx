"use client";
import { useEffect, useState } from "react";
import { Meter } from "./Bits";
import { Glyph } from "./Icon";

// Real-domain reconciliation examples: a messy source line resolves into a
// canonical service with a confidence score and the method that found it.
type Ex = {
  fmt: string;
  raw: string;
  meta: string[];
  canon: string;
  cat: string;
  score: number;
  method: string;
};

const EXAMPLES: Ex[] = [
  {
    fmt: "scan.pdf",
    raw: "А02.020.000.2  Приём кардиолога, первичн.",
    meta: ["код A02.020.000", "OCR"],
    canon: "Приём (осмотр, консультация) врача-кардиолога первичный",
    cat: "Кардиология",
    score: 1.0,
    method: "код-в-код",
  },
  {
    fmt: "price.xlsx",
    raw: "Узи орг.бр.пол + почки",
    meta: ["категория: УЗИ", "таблица"],
    canon: "УЗИ органов брюшной полости и почек",
    cat: "Ультразвук",
    score: 0.92,
    method: "семантика",
  },
  {
    fmt: "list.docx",
    raw: "ОАК (5 diff) развёрн.",
    meta: ["правки Word", "текст"],
    canon: "Общий анализ крови (5 diff), развёрнутый",
    cat: "Лаборатория",
    score: 0.88,
    method: "семантика",
  },
  {
    fmt: "scan.pdf",
    raw: "Дисбактериоз кишечн. (микрофлора)",
    meta: ["категория: —", "OCR"],
    canon: "Исследование микрофлоры кишечника (дисбактериоз)",
    cat: "Лаборатория",
    score: 0.74,
    method: "на ревью",
  },
];

export default function Reconcile() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;
    const t = setInterval(() => setI((x) => (x + 1) % EXAMPLES.length), 3200);
    return () => clearInterval(t);
  }, []);

  const ex = EXAMPLES[i];
  const auto = ex.score >= 0.85;

  return (
    <div className="rec" aria-live="polite">
      <div className="rec-head">
        <span className="dot-row"><i /><i /><i /></span>
        <span className="src"><Glyph.docs size={13} /> {ex.fmt}</span>
      </div>

      <div className="rec-grid" key={i}>
        <div className="rec-col">
          <div className="cap">Источник</div>
          <div className="rec-raw rec-fade">
            <div className="rec-line">{ex.raw}</div>
            <div className="rec-meta">
              {ex.meta.map((m) => (
                <span key={m}>· {m}</span>
              ))}
            </div>
          </div>
        </div>

        <div className="rec-arrow"><Glyph.arrow size={22} /></div>

        <div className="rec-col">
          <div className="cap">Справочник</div>
          <div className="rec-canon rec-fade">
            <div className="rec-line">{ex.canon}</div>
            <div className="rec-meta"><span>{ex.cat}</span></div>
          </div>
        </div>
      </div>

      <div className="rec-foot">
        <span className="verdict" style={{ color: auto ? "var(--accent-ink)" : "var(--amber)" }}>
          {auto ? <Glyph.check size={14} /> : <Glyph.review size={13} />}
          {auto ? "Авто" : "На ревью"} · {ex.method}
        </span>
        <Meter score={ex.score} />
      </div>
    </div>
  );
}
