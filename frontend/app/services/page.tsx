"use client";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import type { Service } from "@/lib/types";
import { PageHead, Loading, ErrorNote } from "@/components/Bits";
import { Glyph } from "@/components/Icon";

type Draft = { canonical_name: string; category: string; icd_code: string };

export default function ServicesPage() {
  const [q, setQ] = useState("");
  const [applied, setApplied] = useState("");
  const { data, error, loading, reload } = useFetch(() => api.services({ q: applied || undefined, limit: 200 }), [applied]);

  const [editId, setEditId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>({ canonical_name: "", category: "", icd_code: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function startEdit(s: Service) {
    setEditId(s.id);
    setErr(null);
    setDraft({ canonical_name: s.canonical_name, category: s.category || "", icd_code: s.icd_code || "" });
  }

  async function save(id: string) {
    if (!draft.canonical_name.trim()) { setErr("Наименование не может быть пустым"); return; }
    setBusy(true); setErr(null);
    try {
      await api.updateService(id, {
        canonical_name: draft.canonical_name.trim(),
        category: draft.category.trim() || null,
        icd_code: draft.icd_code.trim() || null,
      });
      setEditId(null);
      reload();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHead eyebrow="Справочник" title="Услуги">
        <span className="muted" style={{ fontSize: 13 }}>Редактирование позиций справочника</span>
      </PageHead>

      <form
        className="field" style={{ maxWidth: 460 }}
        onSubmit={(e) => { e.preventDefault(); setApplied(q.trim()); }}
      >
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="фильтр по названию…" />
        <button className="btn" style={{ boxShadow: "none", borderLeft: "1px solid var(--rule-strong)" }}>Фильтр</button>
      </form>

      <div style={{ marginTop: 20 }}>
        {loading && <Loading />}
        {error && <ErrorNote error={error} />}
        {data && (
          <div className="panel">
            <table className="table">
              <thead><tr><th style={{ width: 50 }}>#</th><th>Наименование</th><th style={{ width: 200 }}>Категория</th><th style={{ width: 130 }}>Код</th><th style={{ width: 210 }}></th></tr></thead>
              <tbody>
                {data.map((s, i) => {
                  const editing = editId === s.id;
                  return (
                    <tr key={s.id}>
                      <td className="num muted">{i + 1}</td>
                      {editing ? (
                        <>
                          <td><input className="input" style={{ width: "100%" }} value={draft.canonical_name} autoFocus
                            onChange={(e) => setDraft({ ...draft, canonical_name: e.target.value })} /></td>
                          <td><input className="input" style={{ width: "100%" }} value={draft.category} placeholder="—"
                            onChange={(e) => setDraft({ ...draft, category: e.target.value })} /></td>
                          <td><input className="input mono" style={{ width: "100%" }} value={draft.icd_code} placeholder="—"
                            onChange={(e) => setDraft({ ...draft, icd_code: e.target.value })} /></td>
                          <td>
                            <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
                              <button className="btn small primary" disabled={busy} onClick={() => save(s.id)}>
                                <Glyph.check size={13} /> {busy ? "…" : "Сохранить"}
                              </button>
                              <button className="btn small" disabled={busy} onClick={() => { setEditId(null); setErr(null); }}>Отмена</button>
                            </div>
                            {err && <div className="mono" style={{ color: "var(--oxblood)", fontSize: 12, marginTop: 6, textAlign: "right" }}>{err}</div>}
                          </td>
                        </>
                      ) : (
                        <>
                          <td>{s.canonical_name}</td>
                          <td className="muted">{s.category || "—"}</td>
                          <td className="mono muted" style={{ fontSize: 12 }}>{s.icd_code || "—"}</td>
                          <td>
                            <div className="row" style={{ gap: 14, justifyContent: "flex-end" }}>
                              <button className="btn small" onClick={() => startEdit(s)}>Изменить</button>
                              <Link href={`/services/${s.id}?name=${encodeURIComponent(s.canonical_name)}`} className="row" style={{ gap: 6 }}>
                                клиники <Glyph.arrow size={14} />
                              </Link>
                            </div>
                          </td>
                        </>
                      )}
                    </tr>
                  );
                })}
                {data.length === 0 && <tr><td colSpan={5} className="muted" style={{ padding: 30, textAlign: "center" }}>Ничего не найдено</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
