"use client";
import Link from "next/link";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { PageHead, Loading, ErrorNote } from "@/components/Bits";
import { Glyph } from "@/components/Icon";
import { NormDonut, Provenance, DocLedger, CategoryBars } from "@/components/DashCharts";

const fmt = (n: number) => n.toLocaleString("ru-RU");

export default function Dashboard() {
  const { data, error, loading } = useFetch(() => api.dashboard(), []);
  const { data: docs } = useFetch(() => api.dashboardDocs(), []);

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
          {/* slim KPI strip (de-emphasized, no big cliché cards) */}
          <div className="kpi-strip">
            <span className="kpi"><span className="v">{fmt(data.items_total)}</span><span className="l">позиций</span></span>
            <span className="dot" />
            <span className="kpi"><span className="v">{data.normalization.auto_match_pct}%</span><span className="l">сопоставлено авто</span></span>
            <span className="dot" />
            <span className="kpi"><span className="v">{fmt(data.documents_total)}</span><span className="l">прайсов обработано</span></span>
            <span className="dot" />
            <span className="kpi"><span className="v">{fmt(data.services_in_dictionary)}</span><span className="l">услуг в справочнике</span></span>
            <span className="dot" />
            <span className="kpi"><span className="v">{fmt(data.flagged_for_validation)}</span><span className="l">на валидации</span></span>
          </div>

          <div className="dash-2col" style={{ marginTop: 22 }}>
            <div>
              <div className="section-title">Нормализация к справочнику</div>
              <div className="panel pad" style={{ minHeight: 150, display: "flex", alignItems: "center" }}>
                <NormDonut n={data.normalization} total={data.items_total} />
              </div>
            </div>
            <div>
              <div className="section-title">Происхождение данных</div>
              <div className="panel pad" style={{ minHeight: 150, display: "flex", flexDirection: "column", justifyContent: "center" }}>
                {docs ? <Provenance byMethod={docs.by_method} /> : <Loading />}
                <div className="muted" style={{ fontSize: 12.5, marginTop: 16, lineHeight: 1.5 }}>
                  Сканы разбираются vision-моделью в структурные строки — иначе ~21% позиций терялось бы.
                </div>
              </div>
            </div>
          </div>

          <div className="section-title">
            Документы · состав
            <span className="spacer" />
            <Link href="/review" className="row" style={{ gap: 6, fontFamily: "var(--font-body)", textTransform: "none", letterSpacing: 0 }}>
              Очередь верификации <Glyph.arrow size={14} />
            </Link>
          </div>
          {docs ? <DocLedger docs={docs.documents} /> : <Loading />}

          {docs && docs.by_category.length > 0 && (
            <>
              <div className="section-title">Категории услуг · топ {docs.by_category.length}</div>
              <div className="panel pad"><CategoryBars cats={docs.by_category} /></div>
            </>
          )}
        </>
      )}
    </>
  );
}
