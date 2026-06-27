"use client";
import Link from "next/link";
import "./landing.css";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import Reconcile from "@/components/Reconcile";
import { Reveal, Stagger, Counter, ScrollRail, AmbientField, Marquee } from "@/components/Motion";
import { Glyph } from "@/components/Icon";

export default function Landing() {
  const { data } = useFetch(() => api.dashboard(), []);

  // Live numbers with sensible fallbacks for SSR / first paint.
  const itemsTotal = data?.items_total ?? 18415;
  const autoPct = data?.normalization.auto_match_pct ?? 79.7;
  const services = data?.services_in_dictionary ?? 1230;
  const docsTotal = data?.documents_total ?? 10;

  return (
    <div className="lp2">
      <ScrollRail />

      {/* ── NAV ─────────────────────────────────────────────── */}
      <header className="lp2-nav">
        <Link href="/" className="lp2-brand">
          <span className="lp2-mark" aria-hidden>M</span>
          <b>Med<span className="ac">Archive</span></b>
        </Link>
        <nav className="lp2-links">
          <a href="#pipeline">Конвейер</a>
          <a href="#features">Возможности</a>
          <a href="#formats">Форматы</a>
          <Link className="btn small primary" href="/dashboard">Открыть реестр</Link>
        </nav>
      </header>

      {/* ── HERO ────────────────────────────────────────────── */}
      <section className="lp2-hero">
        <AmbientField />

        <div className="lp2-hero-copy">
          <Reveal dir="up">
            <span className="lp2-eyebrow">
              <Glyph.reconcile size={14} /> прайсы клиник → единый реестр
            </span>
          </Reveal>

          <Reveal dir="up" delay={60}>
            <h1 className="lp2-h1">
              Из десятка несхожих прайсов —
              <span className="lp2-h1-accent"> одна цена на одну услугу</span>,
              которой можно доверять.
            </h1>
          </Reveal>

          <Reveal dir="up" delay={140}>
            <p className="lp2-sub">
              MedArchive читает прайс-листы клиник в&nbsp;PDF, сканах, Word и&nbsp;Excel,
              приводит каждую строку к&nbsp;справочнику услуг и&nbsp;проставляет оценку
              уверенности — чтобы цены сходились, а&nbsp;не спорили друг с&nbsp;другом.
            </p>
          </Reveal>

          <Reveal dir="up" delay={220}>
            <div className="lp2-cta-row">
              <Link className="btn primary lg" href="/documents">
                <Glyph.upload size={16} /> Загрузить прайс
              </Link>
              <Link className="btn lg" href="/search">
                <Glyph.find size={16} /> Искать услугу
              </Link>
            </div>
          </Reveal>

          <Reveal dir="up" delay={300}>
            <div className="lp2-trust">
              <div className="lp2-stat">
                <div className="lp2-stat-v tnum">
                  <Counter value={itemsTotal} />
                </div>
                <div className="lp2-stat-k">позиций в реестре</div>
              </div>
              <div className="lp2-stat">
                <div className="lp2-stat-v tnum">
                  <Counter value={autoPct} decimals={1} suffix="%" />
                </div>
                <div className="lp2-stat-k">сопоставлено авто</div>
              </div>
              <div className="lp2-stat">
                <div className="lp2-stat-v tnum">
                  <Counter value={services} />
                </div>
                <div className="lp2-stat-k">услуг в справочнике</div>
              </div>
            </div>
          </Reveal>
        </div>

        <div className="lp2-hero-instrument">
          <Reveal dir="left" delay={160}>
            <Reconcile />
          </Reveal>
          <Reveal dir="up" delay={320}>
            <div className="lp2-legend">
              <span><i className="d hi" /> код-в-код — точное совпадение</span>
              <span><i className="d mid" /> семантика — по смыслу</span>
              <span><i className="d lo" /> на ревью — спорное</span>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── FORMATS MARQUEE ─────────────────────────────────── */}
      <section className="lp2-band" id="formats" aria-label="Форматы источников">
        <div className="lp2-band-label">
          <span className="lp2-eyebrow plain">Берёт прайс в любом виде</span>
        </div>
        <Marquee speed={34}>
          {[
            { tag: "PDF", t: "таблицы и текстовый слой" },
            { tag: "СКАН · OCR", t: "rus + kaz + eng" },
            { tag: "DOCX", t: "Word, в т.ч. с правками" },
            { tag: "XLSX / XLS", t: "Excel любых лет" },
            { tag: "ZIP", t: "пакетная загрузка" },
          ].map((f) => (
            <span className="lp2-fmt" key={f.tag}>
              <span className="lp2-fmt-tag">{f.tag}</span>
              <span className="lp2-fmt-t">{f.t}</span>
            </span>
          ))}
        </Marquee>
      </section>

      {/* ── PIPELINE ────────────────────────────────────────── */}
      <section className="lp2-section" id="pipeline">
        <Reveal dir="up">
          <div className="lp2-eyebrow plain">Конвейер обработки</div>
          <h2 className="lp2-h2">Пять шагов от файла до строки реестра</h2>
          <p className="lp2-lede">
            Каждый документ проходит один и&nbsp;тот же путь — с&nbsp;любым форматом
            и&nbsp;качеством скана. Номера здесь заслужены порядком, а&nbsp;не для красоты.
          </p>
        </Reveal>

        <div className="lp2-pipe">
          <div className="lp2-pipe-rail" aria-hidden />
          <Stagger className="lp2-pipe-grid" step={110}>
            {[
              { n: "01", ic: <Glyph.docs size={20} />, h: "Приём", p: "PDF, скан, Word или Excel. Дубликаты отсекаются по хэшу содержимого." },
              { n: "02", ic: <Glyph.scan size={20} />, h: "Извлечение", p: "Таблицы, текст и OCR для сканов — адаптивно под каждую страницу." },
              { n: "03", ic: <Glyph.tag size={20} />, h: "Позиции и цены", p: "Строки, тарифные колонки и валюта приводятся к тенге." },
              { n: "04", ic: <Glyph.reconcile size={20} />, h: "Нормализация", p: "Сопоставление со справочником: сначала код-в-код, затем семантика." },
              { n: "05", ic: <Glyph.shield size={20} />, h: "Контроль и версии", p: "Восемь правил валидации; история цен хранится по версиям." },
            ].map((s) => (
              <div className="lp2-step" key={s.n}>
                <div className="lp2-step-head">
                  <span className="lp2-step-n tnum">{s.n}</span>
                </div>
                <div className="lp2-step-ic">{s.ic}</div>
                <h3>{s.h}</h3>
                <p>{s.p}</p>
              </div>
            ))}
          </Stagger>
        </div>
      </section>

      {/* ── FEATURES ────────────────────────────────────────── */}
      <section className="lp2-section alt" id="features">
        <Reveal dir="up">
          <div className="lp2-eyebrow plain">Возможности</div>
          <h2 className="lp2-h2">Данные, которым доверяют</h2>
          <p className="lp2-lede">
            Не «чёрный ящик», а&nbsp;инструмент: каждое решение видно, спорное —&nbsp;на руках
            у&nbsp;человека, ничего не теряется.
          </p>
        </Reveal>

        <div className="lp2-feats">
          {[
            {
              ic: <Glyph.reconcile size={22} />,
              h: "Нормализация с оценкой",
              p: "Каждое совпадение получает балл уверенности. Высокие проходят автоматически, спорные уходят в очередь верификации с ранжированными подсказками.",
            },
            {
              ic: <Glyph.shield size={22} />,
              h: "Валидация и версии",
              p: "Восемь правил ловят аномалии цен, пропуски и сомнительные строки. Каждое изменение цены — новая версия, прежнее значение остаётся в истории.",
            },
            {
              ic: <Glyph.find size={22} />,
              h: "Поиск и сравнение",
              p: "Полнотекстовый поиск с морфологией и устойчивостью к опечаткам. Одна услуга — цены всех клиник рядом, для честного сравнения.",
            },
          ].map((f, k) => (
            <Reveal key={f.h} dir="up" delay={k * 90}>
              <div className="lp2-feat lift">
                <div className="lp2-feat-ic">{f.ic}</div>
                <h3>{f.h}</h3>
                <p>{f.p}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── CLOSING CTA ─────────────────────────────────────── */}
      <section className="lp2-close">
        <AmbientField dots={false} />
        <Reveal dir="up">
          <div className="lp2-eyebrow plain center">
            {docsTotal.toLocaleString("ru-RU")} документов уже в&nbsp;реестре
          </div>
          <h2 className="lp2-close-h">
            Загрузите прайс — и&nbsp;увидите разбор
            <span className="lp2-h1-accent"> в реальном времени.</span>
          </h2>
          <p className="lp2-close-sub">
            Перетащите файл и&nbsp;наблюдайте, как страница превращается в&nbsp;строки
            реестра с&nbsp;оценкой уверенности на&nbsp;каждой.
          </p>
          <div className="lp2-cta-row center">
            <Link className="btn primary lg" href="/documents">
              <Glyph.upload size={16} /> Загрузить прайс
            </Link>
            <Link className="btn lg" href="/dashboard">
              <Glyph.board size={16} /> Открыть реестр
            </Link>
          </div>
        </Reveal>
      </section>

      <footer className="lp2-foot">
        <span>MedArchive · реестр услуг и цен клиник-партнёров</span>
        <span className="mono">FastAPI · PostgreSQL · Next.js</span>
      </footer>
    </div>
  );
}
