"use client";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { PageHead, Loading, ErrorNote, StatusBadge } from "@/components/Bits";
import { Glyph } from "@/components/Icon";
import ParseProgress from "@/components/ParseProgress";

const METHOD_RU: Record<string, string> = {
  table: "таблица", ocr: "OCR", words: "текст", lines: "строки", text: "текст", line_items: "строки",
  pdf_text: "PDF · текст", pdf_ocr: "PDF · OCR", pdf_table: "PDF · таблица", xlsx: "Excel", docx: "Word", xls: "Excel",
};

export default function DocumentsPage() {
  const { data, error, loading, reload } = useFetch(() => api.documents(), []);
  const [over, setOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <>
      <PageHead eyebrow="Источники · загрузка" title="Загрузка и обработка прайсов" />

      {file ? (
        <ParseProgress
          file={file}
          onComplete={reload}
          onClose={() => setFile(null)}
        />
      ) : (
        <div
          className={`dropzone ${over ? "over" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) setFile(f); }}
        >
          <div className="row" style={{ justifyContent: "center", marginBottom: 12, color: "var(--accent)" }}>
            <Glyph.upload size={30} />
          </div>
          <div style={{ fontSize: 17, marginBottom: 4, fontWeight: 600 }}>Перетащите прайс-лист сюда</div>
          <div className="muted" style={{ fontSize: 13, marginBottom: 18 }}>
            PDF · DOCX · XLSX · XLS · ZIP
          </div>
          <button className="btn primary" onClick={() => inputRef.current?.click()}>
            <Glyph.docs size={15} /> Выбрать файл
          </button>
          <input
            ref={inputRef} type="file" hidden
            accept=".pdf,.docx,.xlsx,.xls,.zip"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); e.target.value = ""; }}
          />
        </div>
      )}

      <div className="section-title">Обработанные документы</div>
      {loading && <Loading />}
      {error && <ErrorNote error={error} />}
      {data && (
        <div className="panel">
          <table className="table">
            <thead>
              <tr><th>Файл</th><th style={{ width: 90 }}>Формат</th><th style={{ width: 70 }} className="num">Год</th><th style={{ width: 130 }}>Статус</th><th>Метод извлечения</th></tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.id}>
                  <td>{d.source_filename}</td>
                  <td className="mono muted" style={{ fontSize: 12 }}>{d.file_format}</td>
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
              {data.length === 0 && <tr><td colSpan={5} className="muted" style={{ padding: 30, textAlign: "center" }}>Документов пока нет</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
