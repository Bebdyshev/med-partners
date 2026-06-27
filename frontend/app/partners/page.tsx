"use client";
import Link from "next/link";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { PageHead, Loading, ErrorNote } from "@/components/Bits";
import { Glyph } from "@/components/Icon";
import { Stagger } from "@/components/Motion";
import "@/app/discovery.css";

export default function PartnersPage() {
  const { data, error, loading } = useFetch(() => api.partners(), []);
  const active = data?.filter((p) => p.is_active).length ?? 0;

  return (
    <>
      <PageHead eyebrow="Партнёры" title="Клиники-партнёры">
        {data && (
          <span className="muted" style={{ fontSize: 13, fontFamily: "var(--mono)" }}>
            {data.length} клиник · {active} активных
          </span>
        )}
      </PageHead>
      {loading && <Loading />}
      {error && <ErrorNote error={error} />}
      {data && (
        <Stagger className="disc-partners" step={50}>
          {data.map((p) => (
            <Link
              key={p.id}
              href={`/partners/${p.id}?name=${encodeURIComponent(p.display_name)}`}
              className={`disc-pcard ${p.is_active ? "" : "disc-archived"}`}
            >
              <div className="disc-pcard-top">
                <span className="disc-pcard-code">{p.code}</span>
                {p.is_active
                  ? <span className="badge green">активен</span>
                  : <span className="badge">архив</span>}
              </div>
              <div className="disc-pcard-name">{p.display_name}</div>
              <div className="disc-pcard-legal">{p.legal_name || "юр. лицо не указано"}</div>
              <div className="disc-pcard-foot">
                прайс клиники <span className="disc-gw-arrow"><Glyph.arrow size={14} /></span>
                {p.city && <span className="disc-pcard-city">{p.city}</span>}
              </div>
            </Link>
          ))}
          {data.length === 0 && <div className="empty">Партнёров пока нет</div>}
        </Stagger>
      )}
    </>
  );
}
