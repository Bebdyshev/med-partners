# MedArchive — демонстрационный сценарий (requests)

Готовый порядок запросов для показа трекеру: загрузка документа → обработка →
поиск → цены по клиникам → очередь верификации → ручной матч → дашборд.

## 0. Подготовка

Запусти сервер (быстрый режим — fuzzy без эмбеддингов, чтобы ответы были мгновенными):

```bash
cd backend
export PATH="/opt/homebrew/bin:$PATH"
export DATABASE_URL="postgresql+psycopg2://medarchive:medarchive@localhost:5433/medarchive"
export STORAGE_DIR="$(pwd)/storage"
export USE_EMBEDDINGS=false
.venv/bin/uvicorn app.main:app --port 8000
```

Базовый URL: **`http://localhost:8000`** · Swagger: **`http://localhost:8000/docs`**

> В Yaak проще всего: **Import → OpenAPI** из `http://localhost:8000/openapi.json` — подтянет все эндпоинты. Ниже — что и в каком порядке нажимать.

Файл для загрузки уже подготовлен: `demo/Клиника 99 прайс 2026.xlsx`
(шапка спрятана под «шапкой-бланком», 2 тарифа РК/СНГ — демонстрирует поиск заголовка и тарифы).

---

## 1. Здоровье сервиса
```
GET http://localhost:8000/health
```
```bash
curl -s http://localhost:8000/health
```

## 2. Дашборд ДО загрузки (метрики)
```
GET http://localhost:8000/dashboard/stats
```
```bash
curl -s http://localhost:8000/dashboard/stats
```

## 3. 📤 ЗАГРУЗКА ДОКУМЕНТА  ← ключевой шаг
Синхронная обработка (`asynchronous=false`) — обработается сразу, без воркера.

- **Method:** `POST`
- **URL:** `http://localhost:8000/upload?asynchronous=false`
- **Body:** тип `Multipart Form` → поле `file` (тип File) → выбрать `demo/Клиника 99 прайс 2026.xlsx`

```bash
curl -s -F "file=@demo/Клиника 99 прайс 2026.xlsx" \
  "http://localhost:8000/upload?asynchronous=false"
```
Ответ: `{"created":["<DOC_ID>"], "skipped_duplicates":0, "queued":true}` — **скопируй `DOC_ID`**.

> Покажи дедуп: повтори тот же запрос → `"skipped_duplicates":1` (файл с тем же хэшем не обрабатывается дважды).
> Вариант с очередью: `asynchronous=true` (нужен запущенный Celery-воркер + Redis).

## 4. Статус обработки загруженного документа
```
GET http://localhost:8000/documents/<DOC_ID>
```
```bash
curl -s http://localhost:8000/documents/<DOC_ID>
```
Покажет `status: done/needs_review`, `method_summary: {"xlsx": 4}`, лог.

## 5. Прайс загруженной клиники (с тарифами)
Сначала найди partner_id новой клиники (код «Клиника 99»):
```bash
curl -s "http://localhost:8000/partners" | python3 -m json.tool | grep -B2 "Клиника 99"
```
Затем:
```
GET http://localhost:8000/partners/<PARTNER_ID>/services
```
Видно 4 услуги с двумя тарифами (resident_kzt / near_abroad) и статусом нормализации.

---

## 6. 🔎 Поиск услуги
```
GET http://localhost:8000/search?q=кардиолог
```
```bash
curl -s -G "http://localhost:8000/search" --data-urlencode "q=кардиолог"
```
FTS с морфологией русского. Скопируй `id` интересующей услуги.

## 7. ⭐ Кто оказывает услугу и по какой цене (главный эндпоинт ТЗ)
Пример: «Дисбактериоз» — её оказывают **5 клиник под 5 разными названиями**,
сведёнными в одну услугу:
```
GET http://localhost:8000/services/4df190d6-a878-4608-b114-52930d1f54da/partners
```
```bash
curl -s http://localhost:8000/services/4df190d6-a878-4608-b114-52930d1f54da/partners
```
Возвращает (цены от дешёвых к дорогим — наглядно демонстрирует нормализацию + сравнение):
```
• Клиника 2 | Анализ на дисбактериоз кишечника        | 468 ₸
• Клиника 1 | Бак. посев кала на дисбактериоз         | 8 140 ₸
• Клиника 6 | Бактериологическое исследование …       | 9 481 ₸
• Клиника 7 | Исследование на кишечный дисбактериоз   | 14 700 ₸
• Клиника 8 | Бактериологическое исследование …       | 15 480 ₸
```
> Это и есть доказательство нормализации: 5 разных формулировок → одна услуга.

## 8. Полный прайс конкретной клиники (богатые 4 тарифа — Клиника 6)
```
GET http://localhost:8000/partners/1b5957bf-877d-46c7-b4a6-bcb32c1b0b8b/services?limit=5
```
```bash
curl -s "http://localhost:8000/partners/1b5957bf-877d-46c7-b4a6-bcb32c1b0b8b/services?limit=5"
```
Видно 4 тарифа: без НДС / РК / СНГ / дальнее зарубежье — с исходными подписями колонок.

---

## 9. Очередь верификации (несопоставленные + кандидаты)
```
GET http://localhost:8000/unmatched?limit=10
```
```bash
curl -s "http://localhost:8000/unmatched?limit=10"
```
Каждая позиция идёт с ранжированными подсказками из справочника.

## 10. ✍️ Ручное сопоставление (оператор подтверждает + система учит синоним)
Возьми `item_id` из ответа шага 9 (любую позицию очереди) и сопоставь, например, с «Прием кардиолога».

- **Method:** `POST`
- **URL:** `http://localhost:8000/match`
- **Headers:** `Content-Type: application/json`
- **Body (JSON):**
```json
{
  "item_id": "0df80c41-7f79-4421-9da7-84c6160e63ba",
  "service_id": "1ac91652-233d-40e7-b5d5-f1cf539c5d6d",
  "decided_by": "operator@clinic.kz",
  "note": "подтверждено вручную"
}
```
```bash
curl -s -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{"item_id":"0df80c41-7f79-4421-9da7-84c6160e63ba","service_id":"1ac91652-233d-40e7-b5d5-f1cf539c5d6d","decided_by":"operator@clinic.kz"}'
```
> Альтернатива — создать новую услугу справочника: вместо `service_id` передать
> `"create_name": "Название услуги", "category": "Категория"`.

После матча позиция становится `match_status=manual`, `is_verified=true`, а её
написание сохраняется как синоним (следующие документы матчатся автоматически).

## 11. Дашборд ПОСЛЕ (показать, что метрики изменились)
```
GET http://localhost:8000/dashboard/stats
```

---

## Краткий «сухой» список (для шпаргалки)

| # | Запрос | Что показывает |
|---|--------|----------------|
| 1 | `GET /health` | сервис жив |
| 2 | `GET /dashboard/stats` | метрики до |
| 3 | `POST /upload?asynchronous=false` (file) | **загрузка и обработка дока** |
| 4 | `GET /documents/{id}` | статус обработки |
| 5 | `GET /partners/{id}/services` | прайс загруженной клиники |
| 6 | `GET /search?q=кардиолог` | поиск |
| 7 | `GET /services/{id}/partners` | **кто оказывает + цены** |
| 8 | `GET /partners/{id}/services` | 4 тарифа клиники |
| 9 | `GET /unmatched` | очередь верификации |
| 10 | `POST /match` | ручной матч + обучение |
| 11 | `GET /dashboard/stats` | метрики после |

### Готовые ID (из текущей БД)
- Клиника 6 (4 тарифа): `1b5957bf-877d-46c7-b4a6-bcb32c1b0b8b`
- Услуга «Дисбактериоз» (5 клиник, чистая нормализация): `4df190d6-a878-4608-b114-52930d1f54da`
- Услуга «Прием кардиолога»: `1ac91652-233d-40e7-b5d5-f1cf539c5d6d`
- Позиция для ручного матча: `0df80c41-7f79-4421-9da7-84c6160e63ba`

> ⚠️ ID привязаны к текущему снимку БД. Если переинициализируешь БД — возьми свежие
> из Swagger (`/search`, `/partners`) или из `cli report`.
