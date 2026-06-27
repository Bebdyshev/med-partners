"use client";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import type { Service } from "@/lib/types";
import { PageHead, Loading, ErrorNote } from "@/components/Bits";
import { Glyph } from "@/components/Icon";
import { Reveal } from "@/components/Motion";
import "@/app/discovery.css";

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
        <span className="muted" style={{ fontSize: 13 }}>Эталонный реестр — редактирование позиций</span>
      </PageHead>

      <div className="disc-reg-toolbar">
        <form
          className="field" style={{ maxWidth: 460, flex: 1, minWidth: 240 }}
          onSubmit={(e) => { e.preventDefault(); setApplied(q.trim()); }}
        >
          <span style={{ display: "grid", placeItems: "center", paddingLeft: 14, color: "var(--muted)" }}><Glyph.find size={16} /></span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="фильтр по названию услуги…" />
          <button className="btn" style={{ boxShadow: "none", borderLeft: "1px solid var(--rule-strong)" }}>Фильтр</button>
        </form>
        {data && <span className="disc-reg-count">{data.length} {applied ? "найдено" : "позиций"}</span>}
      </div>

      <div>
        {loading && <Loading />}
        {error && <ErrorNote error={error} />}
        {data && (
          <Reveal dir="up">
            <div className="disc-reg">
              <div className="disc-reg-row disc-head">
                <div className="disc-reg-idx">#</div>
                <div>Наименование</div>
                <div>Категория</div>
                <div className="disc-col-code">Код МКБ</div>
                <div style={{ textAlign: "right" }}></div>
              </div>

              {data.map((s, i) => {
                const editing = editId === s.id;
                if (editing) {
                  return (
                    <div className="disc-reg-row disc-editing" key={s.id}>
                      <div className="disc-reg-idx">{i + 1}</div>
                      <div>
                        <input className="input" style={{ width: "100%" }} value={draft.canonical_name} autoFocus
                          onChange={(e) => setDraft({ ...draft, canonical_name: e.target.value })} />
                      </div>
                      <div>
                        <input className="input" style={{ width: "100%" }} value={draft.category} placeholder="—"
                          onChange={(e) => setDraft({ ...draft, category: e.target.value })} />
                      </div>
                      <div className="disc-col-code">
                        <input className="input mono" style={{ width: "100%" }} value={draft.icd_code} placeholder="—"
                          onChange={(e) => setDraft({ ...draft, icd_code: e.target.value })} />
                      </div>
                      <div className="disc-reg-actions">
                        <button className="btn small primary" disabled={busy} onClick={() => save(s.id)}>
                          <Glyph.check size={13} /> {busy ? "…" : "Сохранить"}
                        </button>
                        <button className="btn small" disabled={busy} onClick={() => { setEditId(null); setErr(null); }}>Отмена</button>
                      </div>
                      {err && <div className="disc-reg-err">{err}</div>}
                    </div>
                  );
                }
                return (
                  <div className="disc-reg-row" key={s.id}>
                    <div className="disc-reg-idx">{i + 1}</div>
                    <div className="disc-reg-name">{s.canonical_name}</div>
                    <div className="disc-reg-cat">{s.category || <span className="muted">—</span>}</div>
                    <div className="disc-col-code">
                      <span className={`disc-tag-mono ${s.icd_code ? "" : "disc-empty-tag"}`}>{s.icd_code || "—"}</span>
                    </div>
                    <div className="disc-reg-actions">
                      <button className="btn small" onClick={() => startEdit(s)}>Изменить</button>
                      <Link href={`/services/${s.id}?name=${encodeURIComponent(s.canonical_name)}`} className="disc-reg-link">
                        клиники <Glyph.arrow size={14} />
                      </Link>
                    </div>
                  </div>
                );
              })}

              {data.length === 0 && (
                <div style={{ padding: 34, textAlign: "center" }} className="muted">Ничего не найдено</div>
              )}
            </div>
          </Reveal>
        )}
      </div>
    </>
  );
}
