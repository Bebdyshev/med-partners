# MedArchive — архитектура, алгоритм и технологии

Система автоматической обработки прайс-листов медицинских клиник: принимает файл в
любом виде (PDF, скан, Word, Excel, ZIP), извлекает позиции и цены, приводит их к
**единому справочнику услуг**, проставляет оценку уверенности, валидирует и хранит
**версионированную историю цен**. Поверх — поиск, дашборд, страницы услуг/клиник и
консоль верификации для оператора.

---

## 1. Технологический стек

### Backend
| Слой | Технология | Зачем |
|---|---|---|
| API | **FastAPI** + Uvicorn | асинхронный REST, авто-OpenAPI, стриминг (SSE) |
| Валидация DTO | **Pydantic v2** / pydantic-settings | схемы ответов + конфиг из `.env` |
| ORM | **SQLAlchemy 2.0** | модели, запросы, транзакции |
| Миграции | **Alembic** | схема БД + raw-DDL для `tsvector` и векторных колонок |
| БД | **PostgreSQL** | данные + полнотекстовый поиск (FTS) + триграммы (`pg_trgm`) |
| Очередь/кэш | **Celery** + **Redis** | фоновая обработка (опционально) |
| Извлечение | **pdfplumber**, **PyMuPDF (fitz)**, **pytesseract**, **python-docx**, **openpyxl**, **xlrd**, **pandas**, **Pillow** | парсинг всех форматов |
| Нормализация | **RapidFuzz** (fuzzy), **NumPy** (косинус), **OpenAI** (эмбеддинги/LLM) или **sentence-transformers** (локально), **AWS Step Functions** (опциональный serverless-пайплайн) | сопоставление со справочником |

### Frontend
| Слой | Технология |
|---|---|
| Фреймворк | **Next.js 14** (App Router) + **React 18** + **TypeScript** |
| Графики | собственные SVG/CSS-компоненты (без сторонних chart-библиотек) |
| Стриминг | `fetch` + `ReadableStream` (живой парсинг через SSE-поток) |
| Прокси | rewrite `/api/*` → FastAPI (same-origin, без CORS) |

### Инфраструктура
Docker Compose (Postgres + Redis + backend + frontend), nginx-proxy + Let's Encrypt,
CI/CD через GitHub Actions (`appleboy/ssh-action`).

### AI-провайдеры (переключаемые)
- **OpenAI** (по умолчанию): `text-embedding-3-large` (эмбеддинги), `gpt-4o-mini` (LLM-судья и чистка названий), `gpt-4o` (vision-OCR сканов).
- **On-premise**: `LLM_PROVIDER=ollama` → Qwen2.5:7b / Qwen2.5-VL:7b; `EMBEDDING_PROVIDER=sentence_transformers` → `intfloat/multilingual-e5-large`. Полностью без внешних API.
- **Circuit breaker**: при отказе/исчерпании кредитов OpenAI цепь «размыкается» на 120с, и система автоматически деградирует на локальный RapidFuzz — без зависаний.

---

## 2. Модель данных

```
Partner (клиника)
  └─ PriceDocument (загруженный файл: формат, год, hash, статус, method_summary, warnings)
       └─ PriceItem (одна строка прайса: raw_name, raw_code, source_ref,
            match_status, match_score, service_id?, is_active, superseded_by_id?)
            └─ PriceTier (цена в разрезе тарифа: resident_kzt / near_abroad / …,
                 amount_original + currency → amount_kzt)
Service (эталонная услуга справочника: canonical_name, category, icd_code, search_vector, embedding)
  └─ ServiceSynonym (синонимы)
MatchDecision (аудит сопоставления: кандидат, score, метод, accepted/rejected, кто решил)
```

Ключевые перечисления: `ParseStatus` (queued/processing/done/needs_review/error),
`MatchStatus` (auto/manual/review/unmatched), `MatchMethod` (exact/fuzzy/embedding/manual),
`TierType` (типы цен), `MatchAction` (accepted/rejected/created_service).

---

## 3. Конвейер обработки документа

Реализован в `app/services/processing.py::process_document`. Каждый этап шлёт
прогресс-события в живой UI (`progress`-callback) и проверяет флаг отмены (`should_cancel`).

```
Загрузка файла
   │  дедуп по SHA-256; парсинг кода клиники + года из имени файла
   ▼
[1] Извлечение (extract)         ── формат-специфичные плагины (registry)
   │   • PDF: текстовый слой (pdfplumber) → реконструкция таблиц по координатам слов;
   │     скан-страницы → vision-OCR (структурированные строки) или Tesseract
   │   • DOCX/XLSX/XLS: таблицы напрямую
   │   каждая строка получает source_ref (page=3;vision / sheet=…;row=21)
   ▼
[2] Разбор позиций и цен (parse) ── строит PriceItem + PriceTier
   │   • тип тарифа определяется по заголовку колонки (tier_mapper)
   │   • сумма приводится к ₸ (currency.to_kzt)
   ▼
[3] Нормализация (normalize)     ── сопоставление со справочником (см. §4)
   │   → match_status: auto | review | unmatched, match_score
   │   auto-совпадения создают MatchDecision(accepted)
   ▼
[4] Валидация (validate)         ── 7 правил качества (см. §5)
   ▼
[5] Версионирование (version)    ── archive-on-change (см. §6)
   ▼
Статус документа: done (всё auto, без флагов) | needs_review (есть review/unmatched/flagged)
```

Конвейер идёт **двумя проходами** (сначала весь «Разбор», потом вся «Нормализация»),
чтобы оба этапа стримились в UI инкрементально, а не «выдавали всё в конце».

### Serverless-вариант
В `aws/document-pipeline-sfn.json` описана эквивалентная **AWS Step Functions**
state-machine: ValidateUpload → выбор экстрактора (Lambda) → LLMNormalize (Lambda) →
EmbedAndRerank (Fargate, GPU) → StoreResults → SNS-уведомление, с retry/fallback на
каждом шаге. Локальный Celery и serverless-пайплайн взаимозаменяемы.

---

## 4. Алгоритм нормализации (сопоставления со справочником)

`app/normalization/engine.py::Matcher`. Сигналы по убыванию точности:

1. **Code-first** — точное совпадение тарифного кода (`raw_code` или код, найденный
   прямо в названии; учитываются кириллические гомоглифы). Самый надёжный сигнал → `auto`, score 1.0.
2. **Семантический retrieval** — если кода нет:
   - (опц.) **LLM-чистка** названия перед эмбеддингом (`Узи орг.бр.пол+почки` →
     `УЗИ органов брюшной полости и почек`); справочник чистится так же → один «язык».
   - **Эмбеддинг** запроса (L2-нормализованный) → косинус ко всему справочнику.
   - blended `max(cosine, fuzzy)` + **category boost** (+0.08, если категория совпала).
   - **LLM-судья** (`gpt-4o-mini`) проверяет top-k и выдаёт калиброванную уверенность —
     только для позиций в «полосе сомнения» (precision-стадия).
3. **Fallback** — если эмбеддинги/LLM недоступны (нет кредитов, провайдер выключен) →
   чистый **RapidFuzz** локально (через circuit breaker, мгновенно).

Решение порогами (config): `≥ auto_threshold` → **auto**; `≥ review_floor` → **review**
с ранжированными кандидатами; иначе **unmatched**. Кэши на диске: матрица эмбеддингов
справочника (`emb_*.npy`) и LLM-чистка (`llm_norm_cache.json`) — считается один раз.

---

## 5. Валидация ⭐

Цель: каждая позиция получает набор предупреждений/ошибок качества; любой флаг → документ
уходит в `needs_review`, а позиция подсвечивается оператору. Правила **чистые и
независимы от ORM** (`app/validation/rules.py`), что делает их юнит-тестируемыми:
конвейер адаптирует `PriceItem`+тарифы в нейтральный `ValItem` (с контекстом прошлой
версии) и прогоняет через `validate()`.

### Уровни
- `error` — грубое нарушение (пустое имя, неположительная цена). `ValReport.has_error == True`.
- `warning` — подозрение, требует взгляда оператора. `needs_review == True`, если есть хоть один флаг.

### 7 правил (`ALL_RULES`)
| Код | Уровень | Что проверяет |
|---|---|---|
| `empty_name` | error | имя услуги пустое |
| `price_not_positive` | error | цена в любом тарифе `≤ 0` или отсутствует |
| `nonresident_lt_resident` | warning | цена для нерезидента/СНГ/дальнего зар. **меньше**, чем для граждан РК (обычно ошибка распознавания колонок) |
| `future_date` | warning | дата прайса в будущем относительно `today` |
| `duplicate` | warning | дубликат существующей позиции (тот же partner+service+date) |
| `price_anomaly` | warning | резидентская цена изменилась относительно прошлой версии больше, чем на `PRICE_CHANGE_ANOMALY_PCT` (по умолчанию **50%**) |
| `low_confidence` | warning | уверенность извлечения `< 0.65` (типично для OCR-строк) |

Ключевая деталь — `rule_price_anomaly` и `rule_duplicate` работают **на стыке с
версионированием**: в `ValItem` пробрасывается `prev_resident_price` (резидентская цена
предыдущей активной версии той же услуги у той же клиники). Так аномалия цены
вычисляется относительно реальной истории, а не вслепую:

```
delta_pct = |new_resident − prev_resident| / prev_resident × 100
if delta_pct > PRICE_CHANGE_ANOMALY_PCT:  → price_anomaly
```

Найденные предупреждения сохраняются в `PriceItem.warnings` (JSONB) и агрегируются в
`PriceDocument.warnings` — видны в дашборде («помечено на проверку») и в консоли ревью.

---

## 6. Версионирование ⭐ (archive-on-change)

Реализовано в `app/services/versioning.py::supersede_previous`. Принцип: **ничего
никогда не удаляется** — при появлении более свежей цены старая запись помечается
неактивной и связывается с новой. Полная история цен остаётся запрашиваемой бесконечно.

### Как определяется «та же услуга»
- если новая позиция **сопоставлена** (`service_id` задан) → ищем прошлые активные
  позиции той же клиники с тем же `service_id`;
- если ещё **не сопоставлена** → fallback по нормализованному `raw_name`
  (тот же partner + одинаковое `normalize(raw_name)`).

### Правило архивации
Старая активная версия архивируется **только если она строго не новее** новой
(по `effective_date`); недатированные версии тоже архивируются:

```python
if new.effective_date is None or old.effective_date is None
   or old.effective_date <= new.effective_date:
       old.is_active = False
       old.superseded_by_id = new_item.id   # связь «кем заменена»
```

Это защищает от регресса: загрузка старого прайса не «перезатрёт» более свежий.

### Что это даёт
- **`is_active`** — флаг «актуальная версия». Все витрины (поиск, страница услуги,
  дашборд) показывают активные позиции; цепочка `superseded_by_id` восстанавливает
  полную хронологию.
- **История цен** — на странице услуги строится мини-график «динамика цены» (минимум
  по годам) и блок «Цены по годам»; актуальные (свежие) прайсы показываются сверху,
  самое дешёвое из актуальных — первым.
- **База для аномалий** — именно `supersede_previous` + `prev_resident_price`
  обеспечивают правило `price_anomaly` корректной точкой отсчёта.

Версионирование и валидация работают в паре: на каждой позиции конвейер сначала берёт
`prev_resident_price` (прошлая активная версия), валидирует относительно неё, затем
вызывает `supersede_previous`, делая новую позицию активной, а прошлую — архивной.

---

## 7. Поиск

Трёхслойный гибрид (`app/services/search.py`):
1. **Лексический FTS** — PostgreSQL `tsvector` по `canonical_name + category`, с
   **двунаправленным расширением аббревиатур** (`ОАК ↔ общий анализ крови`).
2. **Семантический** — если FTS даёт мало результатов, косинус по эмбеддингам справочника.
3. **Триграммы** (`pg_trgm`) — фолбэк на опечатки.

---

## 8. Живой парсинг и фоновая обработка

- **Стриминг прогресса**: `GET /documents/{id}/process-stream` (SSE-стиль) — этапы,
  посторничный OCR со сканером страницы, живые счётчики авто/проверка/не найдено.
- **Независимость от вкладки**: обработка идёт в daemon-потоке (реестр задач
  `app/services/jobs.py`); поток буферизует события, поэтому перезагрузка/обрыв
  переподключается и реплеит прогресс. Состояние активного документа хранится в
  `localStorage`.
- **Отмена/удаление**: `should_cancel` проверяется между страницами/позициями →
  `CancelledError` → откат сессии; `POST /{id}/cancel`, `DELETE /{id}` (каскад),
  `POST /documents/purge`.
- **Реплей из кэша**: уже обработанный файл (по hash, либо по клинике из имени)
  проигрывает анимацию из сохранённых данных — без вызовов OpenAI; для обрезанного
  файла реплей ограничивается загруженным числом страниц.

---

## 9. Энциклопедия услуг

`backend/app/data/service_descriptions.json` — 100 курируемых описаний услуг (что
исследуется, когда назначается, как подготовиться, длительность). Эндпоинты
`GET /service-descriptions` и `GET /services/{id}/description` (сопоставление по
`canonical_name_pattern`); карточка показывается на странице услуги.

---

## 10. Ключевые эндпоинты

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/upload` | загрузка (dedupe, replay_pages) |
| GET | `/documents/{id}/process-stream` | живой стрим обработки |
| GET | `/documents/{id}/replay-stream` | анимированный реплей из кэша |
| GET | `/documents/{id}/page/{n}` | PNG страницы (рендер локально) |
| POST | `/documents/{id}/cancel`, DELETE `/documents/{id}`, POST `/documents/purge` | управление очередью |
| GET | `/services`, `/services/{id}/partners`, `/services/{id}/description` | справочник услуг |
| GET | `/unmatched`, POST `/match`, `/review/ai-compare`, `/review/bulk-accept` | консоль верификации |
| GET | `/search`, `/dashboard/stats`, `/dashboard/documents`, `/dashboard/partners` | поиск и аналитика |

---

## TL;DR

Файл → извлечение (текст/таблицы/OCR) → разбор позиций и приведение цен к ₸ →
нормализация к справочнику (код → эмбеддинг → LLM-судья, с локальным fallback) →
**валидация 7 правилами качества** → **версионирование archive-on-change** (история
цен, актуальная версия, база для детекции аномалий) → витрины: поиск, дашборд,
страницы услуг/клиник, консоль ревью. Весь процесс — живой стрим, переживающий
перезагрузку, с возможностью отмены и реплея из кэша.
