"use client";
import Link from "next/link";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import Reconcile from "@/components/Reconcile";
import Reveal from "@/components/Reveal";
import { Glyph } from "@/components/Icon";

export default function Landing() {
  const { data } = useFetch(() => api.dashboard(), []);
  const fmt = (n?: number) => (n == null ? "—" : n.toLocaleString("ru-RU"));

  const trust = [
    { v: data ? fmt(data.items_total) : "14 554", k: "позиций в реестре" },
    { v: data ? `${data.normalization.auto_match_pct}%` : "55%", k: "сопоставлено авто" },
    { v: data ? fmt(data.services_in_dictionary) : "1 230", k: "услуг в справочнике" },
  ];

  return (
    <div className="lp">
      <header className="lp-nav">
        <Link href="/" className="brand" style={{ color: "var(--ink)" }}>
          <span className="mark" aria-hidden>M</span>
          <b>Med<span className="ac">Archive</span></b>
        </Link>
        <nav className="links">
          <a href="#how">Как это работает</a>
          <a href="#features">Возможности</a>
          <a href="#formats">Форматы</a>
          <Link className="btn small primary" href="/dashboard">Открыть реестр</Link>
        </nav>
      </header>

      {/* HERO — the thesis is a live reconciliation */}
      <section className="hero">
        <div>
          <span className="hero-eyebrow"><Glyph.reconcile size={14} /> прайсы клиник → единый реестр</span>
          <h1>
            Из десятка несхожих прайсов —<br />
            <span className="lead">одна цена на одну услугу.</span>
          </h1>
          <p className="sub">
            MedArchive читает прайс-листы клиник в PDF, сканах, Word и Excel, приводит каждую
            строку к справочнику услуг и проставляет оценку уверенности — чтобы ценам можно было доверять.
          </p>
          <div className="cta">
            <Link className="btn primary lg" href="/documents"><Glyph.upload size={16} /> Загрузить прайс</Link>
            <Link className="btn lg" href="/search"><Glyph.find size={16} /> Искать услугу</Link>
          </div>
          <div className="trust">
            {trust.map((t) => (
              <div key={t.k}>
                <div className="t-v num">{t.v}</div>
                <div className="t-k">{t.k}</div>
              </div>
            ))}
          </div>
        </div>

        <Reconcile />
      </section>

      {/* HOW — a real ordered pipeline, so the numbering is earned */}
      <section className="lp-section alt" id="how">
        <Reveal>
          <div className="lp-eyebrow">Конвейер обработки</div>
          <h2>Пять шагов от файла до строки реестра</h2>
          <p className="lede">
            Каждый документ проходит один и тот же путь — с любым форматом и качеством скана.
          </p>
        </Reveal>
        <Reveal delay={80}>
          <div className="steps">
            {[
              { n: "01", ic: <Glyph.docs size={20} />, h: "Приём файла", p: "PDF, скан, Word или Excel. Дубликаты отсекаются по хэшу." },
              { n: "02", ic: <Glyph.scan size={20} />, h: "Извлечение", p: "Таблицы, текст и OCR для сканов — адаптивно под страницу." },
              { n: "03", ic: <Glyph.tag size={20} />, h: "Позиции и цены", p: "Строки, тарифные колонки и валюта приводятся к тенге." },
              { n: "04", ic: <Glyph.reconcile size={20} />, h: "Нормализация", p: "Сопоставление со справочником: код-в-код, затем семантика." },
              { n: "05", ic: <Glyph.shield size={20} />, h: "Контроль и версии", p: "8 правил валидации; история цен сохраняется по версиям." },
            ].map((s) => (
              <div className="step" key={s.n}>
                <div className="n">{s.n}</div>
                <div className="ic" style={{ marginTop: 12 }}>{s.ic}</div>
                <h3>{s.h}</h3>
                <p>{s.p}</p>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      {/* FEATURES */}
      <section className="lp-section" id="features">
        <Reveal>
          <div className="lp-eyebrow">Возможности</div>
          <h2>Данные, которым доверяют</h2>
        </Reveal>
        <div className="feats">
          {[
            { ic: <Glyph.reconcile size={20} />, h: "Нормализация с оценкой", p: "Каждое совпадение получает балл уверенности. Высокие — автоматически, спорные — в очередь верификации с ранжированными подсказками." },
            { ic: <Glyph.shield size={20} />, h: "Валидация и версии", p: "Восемь правил ловят аномалии цен, пропуски и сомнительные строки. Каждое изменение цены — новая версия, старое не теряется." },
            { ic: <Glyph.find size={20} />, h: "Поиск и сравнение", p: "Полнотекстовый поиск с морфологией и устойчивостью к опечаткам. Одна услуга — цены всех клиник рядом." },
          ].map((f, k) => (
            <Reveal key={f.h} delay={k * 90}>
              <div className="feat">
                <div className="ic">{f.ic}</div>
                <h3>{f.h}</h3>
                <p>{f.p}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* FORMATS */}
      <section className="lp-section alt" id="formats">
        <Reveal>
          <div className="lp-eyebrow">Форматы источников</div>
          <h2>Берёт прайс в любом виде</h2>
          <p className="lede">Структурированные таблицы и хаотичные сканы — один пайплайн извлечения.</p>
          <div className="formats">
            {[
              { tag: "PDF", t: "таблицы и текстовый слой" },
              { tag: "СКАН", t: "OCR · rus + kaz + eng" },
              { tag: "DOCX", t: "Word, в т.ч. правки" },
              { tag: "XLSX / XLS", t: "Excel любых лет" },
              { tag: "ZIP", t: "пакетная загрузка" },
            ].map((f) => (
              <span className="fmt" key={f.tag}>
                <span className="tag">{f.tag}</span>
                <span className="muted" style={{ fontSize: 13 }}>{f.t}</span>
              </span>
            ))}
          </div>
        </Reveal>
      </section>

      {/* CTA */}
      <section className="lp-cta">
        <Reveal>
          <h2>Загрузите прайс — увидите разбор в реальном времени</h2>
          <p className="sub">Перетащите файл и наблюдайте, как страница превращается в строки реестра с оценкой уверенности.</p>
          <div className="cta" style={{ justifyContent: "center" }}>
            <Link className="btn primary lg" href="/documents"><Glyph.upload size={16} /> Загрузить прайс</Link>
            <Link className="btn lg" href="/dashboard"><Glyph.board size={16} /> Открыть реестр</Link>
          </div>
        </Reveal>
      </section>

      <footer className="lp-foot">
        <span>MedArchive · реестр услуг и цен клиник-партнёров</span>
        <span>FastAPI · PostgreSQL · Next.js</span>
      </footer>
    </div>
  );
}
