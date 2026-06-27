"use client";
import "./dashboard.css";
import Link from "next/link";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { useInView } from "@/lib/motion";
import { PageHead, Loading, ErrorNote } from "@/components/Bits";
import { Reveal, Counter } from "@/components/Motion";
import { Glyph } from "@/components/Icon";
import { NormDonut, Provenance, DocLedger, CategoryBars } from "@/components/DashCharts";

const fmt = (n: number) => n.toLocaleString("ru-RU");

/** Thin confidence meter under the lead stat — fills on view. */
function LeadMeter({ value }: { value: number }) {
  const [ref, inView] = useInView<HTMLDivElement>({ threshold: 0.4 });
  return (
    <div className="dsh-meter" ref={ref} aria-hidden>
      <i style={{ width: inView ? `${Math.max(0, Math.min(100, value))}%` : 0 }} />
    </div>
  );
}

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
          {/* ---- Hero readout: tabular numerals as the instrument ---- */}
          <Reveal>
            <div className="dsh-readout">
              <div className="dsh-rcell lead">
                <div className="dsh-rk"><span className="tick" style={{ background: "var(--chart-auto)" }} /> сопоставлено авто</div>
                <span className="dsh-rv"><Counter value={data.normalization.auto_match_pct} decimals={1} /><span className="u">%</span></span>
                <LeadMeter value={data.normalization.auto_match_pct} />
                <div className="dsh-rsub">{fmt(data.normalization.auto)} позиций сведены к справочнику автоматически</div>
              </div>

              <div className="dsh-rcell">
                <div className="dsh-rk">позиций</div>
                <span className="dsh-rv"><Counter value={data.items_total} /></span>
                <div className="dsh-rsub">{fmt(data.items_active)} активных</div>
              </div>

              <div className="dsh-rcell">
                <div className="dsh-rk">прайсов</div>
                <span className="dsh-rv"><Counter value={data.documents_total} /></span>
                <div className="dsh-rsub">обработано в реестре</div>
              </div>

              <div className="dsh-rcell">
                <div className="dsh-rk">справочник</div>
                <span className="dsh-rv"><Counter value={data.services_in_dictionary} /></span>
                <div className="dsh-rsub">канонических услуг</div>
              </div>

              <div className="dsh-rcell flag">
                <div className="dsh-rk"><span className="tick" style={{ background: "var(--amber)" }} /> на валидации</div>
                <span className="dsh-rv"><Counter value={data.flagged_for_validation} /></span>
                <div className="dsh-rsub"><Link href="/review" className="dsh-seclink">в очередь верификации <Glyph.arrow size={13} /></Link></div>
              </div>
            </div>
          </Reveal>

          {/* ---- Normalization + provenance instruments ---- */}
          <div className="section-title">Нормализация к справочнику</div>
          <Reveal>
            <div className="dsh-grid">
              <div className="dsh-card">
                <div className="dsh-cardhead">
                  <span className="t">Распределение совпадений</span>
                  <span className="s">{fmt(data.items_total)} позиций</span>
                </div>
                <NormDonut n={data.normalization} total={data.items_total} />
              </div>

              <div className="dsh-card">
                <div className="dsh-cardhead">
                  <span className="t">Происхождение данных</span>
                  <span className="s">метод извлечения</span>
                </div>
                {docs ? <Provenance byMethod={docs.by_method} /> : <Loading />}
              </div>
            </div>
          </Reveal>

          {/* ---- Document ledger ---- */}
          <div className="section-title">
            Документы · состав
            <span className="spacer" />
            <Link href="/review" className="dsh-seclink">
              Очередь верификации <Glyph.arrow size={14} />
            </Link>
          </div>
          {docs ? <DocLedger docs={docs.documents} /> : <Loading />}

          {/* ---- Top categories ---- */}
          {docs && docs.by_category.length > 0 && (
            <>
              <div className="section-title">Категории услуг · топ {docs.by_category.length}</div>
              <Reveal>
                <div className="dsh-card"><CategoryBars cats={docs.by_category} /></div>
              </Reveal>
            </>
          )}
        </>
      )}
    </>
  );
}
