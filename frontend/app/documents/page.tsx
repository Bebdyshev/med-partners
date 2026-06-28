"use client";
import "../pipeline.css";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { PageHead, Loading, ErrorNote, StatusBadge } from "@/components/Bits";
import { Reveal, AmbientField } from "@/components/Motion";
import { Glyph } from "@/components/Icon";
import ParseProgress from "@/components/ParseProgress";

const METHOD_RU: Record<string, string> = {
  table: "таблица", ocr: "OCR", words: "текст", lines: "строки", text: "текст", line_items: "строки",
  pdf_text: "PDF · текст", pdf_ocr: "PDF · OCR", pdf_table: "PDF · таблица", xlsx: "Excel", docx: "Word", xls: "Excel",
};

const FORMATS: { ic: keyof typeof Glyph; nm: string; sub: string; ext: string }[] = [
  { ic: "docs", nm: "PDF", sub: "текст и таблицы", ext: ".pdf" },
  { ic: "scan", nm: "Скан / фото", sub: "OCR + распознавание", ext: ".pdf" },
  { ic: "docs", nm: "Word", sub: "документы", ext: ".docx" },
  { ic: "table", nm: "Excel", sub: "книги и листы", ext: ".xlsx · .xls" },
  { ic: "layers", nm: "Архив", sub: "пакет файлов", ext: ".zip" },
];

export default function DocumentsPage() {
  const { data, error, loading, reload } = useFetch(() => api.documents(), []);
  const [over, setOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [demo, setDemo] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function runDemo() {
    setDemoBusy(true);
    try {
      const f = await api.demoFile();
      setDemo(true);
      setFile(f);
    } catch (e) {
      alert("Демо-файл недоступен: " + (e as Error).message);
    } finally {
      setDemoBusy(false);
    }
  }

  return (
    <>
      <PageHead eyebrow="Источники · загрузка" title="Загрузка и обработка прайсов" />
      <p className="pipe-lede">
        Бросьте сюда прайс-лист в любом виде — PDF, скан, Word или Excel. Система прочитает файл,
        извлечёт позиции и цены, приведёт их к <b>единому справочнику</b> и проставит оценку уверенности.
      </p>

      {file ? (
        <ParseProgress
          file={file}
          demo={demo}
          onComplete={reload}
          onClose={() => { setFile(null); setDemo(false); }}
        />
      ) : (
        <div
          className={`pipe-drop ${over ? "over" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) setFile(f); }}
        >
          <AmbientField />
          <div className="pipe-drop-glyph"><Glyph.upload size={40} /></div>

          <div className="pipe-drop-main">
            <div className="pipe-kicker">Приём · 01</div>
            <h2>Перетащите прайс-лист сюда</h2>
            <div className="sub">
              {over ? "Отпустите — начнём разбор." : "или выберите файл вручную. Один документ за раз; дубликаты отсеиваются по хэшу."}
            </div>
            <div className="cta-row">
              <button className="btn primary" onClick={() => inputRef.current?.click()}>
                <Glyph.docs size={15} /> Выбрать файл
              </button>
              <button className="btn" onClick={runDemo} disabled={demoBusy}>
                <Glyph.scan size={15} /> {demoBusy ? "Загрузка…" : "Демо: скан-прайс"}
              </button>
              <span className="hint">форматы <span className="kbd">PDF</span> <span className="kbd">DOCX</span> <span className="kbd">XLSX</span> <span className="kbd">ZIP</span></span>
            </div>
            <input
              ref={inputRef} type="file" hidden
              accept=".pdf,.docx,.xlsx,.xls,.zip"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); e.target.value = ""; }}
            />
          </div>

          <div className="pipe-drop-aside">
            <div className="pipe-fmts">
              {FORMATS.map((f, i) => {
                const Ic = Glyph[f.ic];
                return (
                  <div className="pipe-fmt" key={i}>
                    <span className="ic"><Ic size={17} /></span>
                    <span className="nm">{f.nm}<small>{f.sub}</small></span>
                    <span className="ext">{f.ext}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <div className="section-title">Обработанные документы</div>
      {loading && <Loading />}
      {error && <ErrorNote error={error} />}
      {data && (
        <Reveal dir="up">
          <div className="panel">
            <table className="table">
              <thead>
                <tr><th>Файл</th><th style={{ width: 110 }}>Формат</th><th style={{ width: 70 }} className="num">Год</th><th style={{ width: 130 }}>Статус</th><th>Метод извлечения</th></tr>
              </thead>
              <tbody>
                {data.map((d) => (
                  <tr key={d.id}>
                    <td className="pipe-doc-name">{d.source_filename}</td>
                    <td><span className="pipe-fmt-cell">{d.file_format}</span></td>
                    <td className="num muted">{d.year ?? "—"}</td>
                    <td><StatusBadge status={d.status} /></td>
                    <td>
                      <div className="row" style={{ gap: 6 }}>
                        {Object.entries(d.method_summary || {}).map(([k, v]) => (
                          <span className="badge" key={k}>{METHOD_RU[k] || k} · {v}</span>
                        ))}
                        {Object.keys(d.method_summary || {}).length === 0 && <span className="muted">—</span>}
                      </div>
                    </td>
                  </tr>
                ))}
                {data.length === 0 && <tr><td colSpan={5} className="muted" style={{ padding: 30, textAlign: "center" }}>Документов пока нет — загрузите первый прайс-лист выше.</td></tr>}
              </tbody>
            </table>
          </div>
        </Reveal>
      )}
    </>
  );
}
