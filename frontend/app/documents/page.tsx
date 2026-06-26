"use client";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { PageHead, Loading, ErrorNote, StatusBadge } from "@/components/Bits";
import { Glyph } from "@/components/Icon";

export default function DocumentsPage() {
  const { data, error, loading, reload } = useFetch(() => api.documents(), []);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function send(file: File) {
    setBusy(true); setMsg(null);
    try {
      const r = await api.upload(file, false); // inline processing — no worker needed
      if (r.created.length) setMsg(`Загружено и обработано: ${file.name}`);
      else if (r.skipped_duplicates) setMsg(`Дубликат — файл «${file.name}» уже есть в базе (дедуп по хэшу).`);
      reload();
    } catch (e) {
      setMsg("Ошибка: " + (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHead eyebrow="05 · Документы" title="Загрузка и обработка прайсов" />

      <div
        className={`dropzone ${over ? "over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) send(f); }}
      >
        <div className="row" style={{ justifyContent: "center", marginBottom: 10 }}><Glyph.docs size={26} /></div>
        <div style={{ fontSize: 16, marginBottom: 4 }}>Перетащите прайс-лист сюда</div>
        <div className="muted" style={{ fontSize: 13, marginBottom: 16 }}>
          PDF · DOCX · XLSX · XLS · ZIP — или
        </div>
        <button className="btn primary" disabled={busy} onClick={() => inputRef.current?.click()}>
          {busy ? "Обработка…" : "Выбрать файл"}
        </button>
        <input
          ref={inputRef} type="file" hidden
          accept=".pdf,.docx,.xlsx,.xls,.zip"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) send(f); e.target.value = ""; }}
        />
        {msg && <div className="mono" style={{ fontSize: 13, marginTop: 16, color: "var(--ink-2)" }}>{msg}</div>}
      </div>

      <div className="section-title">Обработанные документы</div>
      {loading && <Loading />}
      {error && <ErrorNote error={error} />}
      {data && (
        <div className="panel">
          <table className="table">
            <thead>
              <tr><th>Файл</th><th style={{ width: 80 }}>Формат</th><th style={{ width: 80 }}>Год</th><th style={{ width: 120 }}>Статус</th><th>Метод извлечения</th></tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.id}>
                  <td>{d.source_filename}</td>
                  <td className="mono muted" style={{ fontSize: 12 }}>{d.file_format}</td>
                  <td className="num muted">{d.year ?? "—"}</td>
                  <td><StatusBadge status={d.status} /></td>
                  <td className="mono muted" style={{ fontSize: 12 }}>
                    {Object.entries(d.method_summary || {}).map(([k, v]) => `${k}:${v}`).join("  ") || "—"}
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
