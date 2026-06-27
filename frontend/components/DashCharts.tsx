"use client";
import type { DashboardDocs, DocBreakdown } from "@/lib/types";

const fmt = (n: number) => n.toLocaleString("ru-RU");
const pct = (v: number, t: number) => (t ? (v / t) * 100 : 0);

const METHOD_LABEL: Record<string, string> = {
  xlsx: "таблица", xls: "таблица", docx: "Word", pdf_text: "текст", pdf_ocr: "скан · OCR",
};
const FORMAT_LABEL: Record<string, string> = { xlsx: "Excel", xls: "Excel", docx: "Word", pdf: "PDF", scan_pdf: "скан" };

/* ---------- Normalization donut ---------- */
export function NormDonut({ n, total }: { n: { auto: number; review: number; unmatched: number; manual: number; auto_match_pct: number }; total: number }) {
  const r = 54, C = 2 * Math.PI * r;
  const segs: [string, string, number][] = [
    ["var(--accent)", "Авто", n.auto],
    ["var(--amber)", "На ревью", n.review],
    ["var(--oxblood)", "Без совпадения", n.unmatched],
    ["var(--ink)", "Вручную", n.manual],
  ];
  let off = 0;
  return (
    <div className="donut-wrap">
      <div className="donut">
        <svg width="100%" height="100%" viewBox="0 0 132 132">
          <circle cx="66" cy="66" r={r} fill="none" stroke="var(--paper-3)" strokeWidth="16" />
          {segs.map(([c, , v], i) => {
            const len = pct(v, total) / 100 * C;
            const el = (
              <circle key={i} cx="66" cy="66" r={r} fill="none" stroke={c} strokeWidth="16"
                strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-off} />
            );
            off += len;
            return el;
          })}
        </svg>
        <div className="center"><div className="pct num">{n.auto_match_pct}%</div><div className="cap">авто</div></div>
      </div>
      <div className="dlegend">
        {segs.map(([c, label, v], i) => (
          <div className="row2" key={i}>
            <span className="sw" style={{ background: c }} />
            <span>{label}</span>
            <span className="n">{fmt(v)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------- Extraction provenance (segmented bar) ---------- */
export function Provenance({ byMethod }: { byMethod: Record<string, number> }) {
  const tables = (byMethod.xlsx || 0) + (byMethod.xls || 0);
  const text = (byMethod.docx || 0) + (byMethod.pdf_text || 0);
  const scan = byMethod.pdf_ocr || 0;
  const total = tables + text + scan || 1;
  const segs: [string, string, number][] = [
    ["var(--accent)", "Таблицы", tables],
    ["var(--ink)", "Текст / Word", text],
    ["var(--amber)", "Сканы · OCR/Vision", scan],
  ];
  return (
    <div>
      <div className="seg">
        {segs.map(([c, , v], i) => v > 0 && <i key={i} style={{ width: `${pct(v, total)}%`, background: c }} />)}
      </div>
      <div className="seg-legend">
        {segs.map(([c, label, v], i) => (
          <span key={i}><span className="sw" style={{ background: c }} /> {label} <span className="n">{fmt(v)}</span></span>
        ))}
      </div>
    </div>
  );
}

/* ---------- Document ledger (hero) ---------- */
function LedgerRow({ d }: { d: DocBreakdown }) {
  const t = d.items || 1;
  const autoPct = Math.round(pct(d.auto, t));
  const segs: [string, number][] = [
    ["var(--accent)", d.auto], ["var(--amber)", d.review], ["var(--oxblood)", d.unmatched], ["var(--ink)", d.manual],
  ];
  const methods = Object.entries(d.methods).sort((a, b) => b[1] - a[1]);
  return (
    <div className="lrow">
      <div className="lhead">
        <span className="lname" title={d.source_filename}>{d.source_filename}</span>
        <span className="badge">{FORMAT_LABEL[d.file_format] || d.file_format}</span>
        {methods.map(([m, v]) => (
          <span className="mtag" key={m}>{METHOD_LABEL[m] || m} · {fmt(v)}</span>
        ))}
        <span className="spacer" />
        <span className="ltotal">{fmt(d.items)} поз</span>
        <span className="lauto" style={{ color: autoPct >= 60 ? "var(--accent)" : "var(--amber)" }}>{autoPct}% авто</span>
      </div>
      <div className="lbarrow">
        <span className="lbar">
          {segs.map(([c, v], i) => v > 0 && <i key={i} style={{ width: `${pct(v, t)}%`, background: c }} />)}
        </span>
        <span className="lcount">авто {fmt(d.auto)} · ревью {fmt(d.review)} · без&nbsp;совп. {fmt(d.unmatched)}{d.flagged ? ` · ⚑ ${fmt(d.flagged)}` : ""}</span>
      </div>
    </div>
  );
}

export function DocLedger({ docs }: { docs: DocBreakdown[] }) {
  return <div className="ledger">{docs.map((d) => <LedgerRow key={d.id} d={d} />)}</div>;
}

/* ---------- Top categories ---------- */
export function CategoryBars({ cats }: { cats: DashboardDocs["by_category"] }) {
  const max = Math.max(1, ...cats.map((c) => c.items));
  return (
    <div className="catbars">
      {cats.map((c) => (
        <div className="catrow" key={c.category}>
          <span className="cname" title={c.category}>{c.category}</span>
          <span className="ctrack"><span className="cfill" style={{ width: `${(c.items / max) * 100}%` }} /></span>
          <span className="cnum">{fmt(c.items)}</span>
        </div>
      ))}
    </div>
  );
}
