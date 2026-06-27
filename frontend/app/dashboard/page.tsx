"use client";
import Link from "next/link";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { PageHead, Loading, ErrorNote, StatusBadge } from "@/components/Bits";
import { Glyph } from "@/components/Icon";

export default function Dashboard() {
  const { data, error, loading } = useFetch(() => api.dashboard(), []);

  return (
    <>
      <PageHead eyebrow="Реестр · сводка" title="Состояние реестра">
        <Link className="btn primary" href="/documents">
          <Glyph.upload size={15} /> Загрузить прайс
        </Link>
      </PageHead>

      {loading && <Loading />}
      {error && <ErrorNote error={error} />}

      {data && (
        <>
          <div className="stats">
            <Stat k="Документов" v={data.documents_total} sub="прайс-листов обработано" />
            <Stat k="Позиций" v={data.items_total.toLocaleString("ru-RU")} sub={`${data.items_active.toLocaleString("ru-RU")} актуальных`} />
            <Stat k="Услуг в справочнике" v={data.services_in_dictionary.toLocaleString("ru-RU")} sub="целевой справочник" />
            <Stat k="На валидации" v={data.flagged_for_validation.toLocaleString("ru-RU")} sub="помечено правилами" />
          </div>

          <div className="section-title">Нормализация к справочнику</div>
          <div className="panel pad">
            <NormBar n={data.normalization} total={data.items_total} />
            <div className="row" style={{ marginTop: 18, gap: 22, fontSize: 13 }}>
              <Legend color="var(--accent)" label="Авто" v={data.normalization.auto} />
              <Legend color="var(--amber)" label="На ревью" v={data.normalization.review} />
              <Legend color="var(--oxblood)" label="Без совпадения" v={data.normalization.unmatched} />
              <Legend color="var(--ink)" label="Вручную" v={data.normalization.manual} />
              <div className="spacer" />
              <Link href="/review" className="row" style={{ gap: 6 }}>
                Очередь верификации <Glyph.arrow size={15} />
              </Link>
            </div>
          </div>

          <div className="section-title">Документы по статусу</div>
          <div className="panel pad">
            <div className="row" style={{ gap: 16 }}>
              {Object.entries(data.documents).map(([s, n]) => (
                <span key={s} className="row" style={{ gap: 8 }}>
                  <StatusBadge status={s} /> <span className="num">{n}</span>
                </span>
              ))}
            </div>
          </div>
        </>
      )}
    </>
  );
}

function Stat({ k, v, sub }: { k: string; v: React.ReactNode; sub: string }) {
  return (
    <div className="stat">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
      <div className="sub">{sub}</div>
    </div>
  );
}

function NormBar({ n, total }: { n: { auto: number; review: number; unmatched: number; manual: number; auto_match_pct: number }; total: number }) {
  const seg = (v: number, c: string) => ({ width: `${total ? (v / total) * 100 : 0}%`, background: c });
  return (
    <div>
      <div className="between" style={{ marginBottom: 10 }}>
        <span className="upper muted">распределение {total.toLocaleString("ru-RU")} позиций</span>
        <span className="num" style={{ fontSize: 22, fontWeight: 600 }}>{n.auto_match_pct}% авто</span>
      </div>
      <div style={{ display: "flex", height: 14, borderRadius: 999, overflow: "hidden", background: "var(--paper-3)" }}>
        <i style={seg(n.auto, "var(--accent)")} />
        <i style={seg(n.review, "var(--amber)")} />
        <i style={seg(n.unmatched, "var(--oxblood)")} />
        <i style={seg(n.manual, "var(--ink)")} />
      </div>
    </div>
  );
}

function Legend({ color, label, v }: { color: string; label: string; v: number }) {
  return (
    <span className="row" style={{ gap: 7 }}>
      <span style={{ width: 11, height: 11, borderRadius: 3, background: color }} />
      <span>{label}</span>
      <span className="num muted">{v.toLocaleString("ru-RU")}</span>
    </span>
  );
}
