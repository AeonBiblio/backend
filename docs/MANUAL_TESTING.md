# Ручная проверка API (Swagger / Postman)

Пошаговое руководство для проверки **всех** эндпоинтов AeonBiblio.

**Base URL:** `http://localhost:8000`  
**Swagger UI:** http://localhost:8000/docs  
**ReDoc:** http://localhost:8000/redoc

---

## 1. Подготовка

### Запуск

```powershell
cd "d:\prog\aeon libr\aeon libr"
docker compose up --build
```

Дождитесь, пока `GET /health` вернёт:

```json
{ "status": "ok", "db": true }
```

### Два тестовых пользователя

Для полной проверки нужны минимум **два аккаунта**:

| Роль | email | username | password |
|------|-------|----------|----------|
| Автор | `author@test.com` | `author` | `password123` |
| Читатель | `reader@test.com` | `reader` | `password123` |

Сохраните их `access_token` после логина — они понадобятся дальше.

---

## 2. Swagger — как авторизоваться

1. Откройте http://localhost:8000/docs
2. Выполните `POST /auth/login` для автора
3. Скопируйте `access_token` из ответа
4. Нажмите кнопку **Authorize** (замок вверху справа)
5. Введите: `Bearer <ваш_access_token>` (слово `Bearer` и пробел обязательны)
6. Нажмите **Authorize** → **Close**

Теперь все запросы с замком будут отправляться с токеном.

> Чтобы проверить от имени читателя — повторите шаги 2–5 с токеном читателя.

---

## 3. Postman — как настроить

### Переменные окружения (Environment)

Создайте environment `AeonBiblio Local`:

| Variable | Initial value |
|----------|---------------|
| `base_url` | `http://localhost:8000` |
| `author_token` | *(пусто, заполнится после login)* |
| `reader_token` | *(пусто)* |
| `book_id` | *(пусто, после создания книги)* |
| `plan_id` | *(пусто, после GET /subscriptions/plans)* |
| `readlist_id` | *(пусто)* |
| `review_id` | *(пусто)* |

### Заголовок авторизации

Для защищённых запросов добавьте заголовок:

```
Authorization: Bearer {{author_token}}
```

или `{{reader_token}}` — в зависимости от сценария.

### Автосохранение токена (опционально)

В запросе `POST {{base_url}}/auth/login` на вкладке **Tests**:

```javascript
const data = pm.response.json();
pm.environment.set("author_token", data.access_token);
```

---

## 4. Рекомендуемый порядок проверки

Выполняйте запросы **в этом порядке** — так каждый следующий шаг использует данные из предыдущего.

```
1. Health
2. Auth (register ×2, login ×2)
3. Users (профиль, пароль, аватар, payment profile)
4. Books — автор создаёт книгу, загружает файлы, submit
5. Опубликовать книгу вручную (SQL, см. ниже)
6. Books — читатель: access, content, отзывы, теги
7. Subscriptions — подписка читателя
8. Earnings — покупка, чтение по подписке, баланс автора
9. Library — статусы и readlists
10. Recommendations, публичный профиль
```

### Опубликовать книгу без модерации (dev)

Модерация в API пока **не реализована**. После `POST /books/{id}/submit` книга в статусе `pending`. Для тестов чтения/покупки опубликуйте вручную:

```powershell
docker compose exec -T db psql -U aeon -d aeonbiblio -c "UPDATE books SET status='published', published_at=NOW() WHERE id='<BOOK_ID>';"
```

Замените `<BOOK_ID>` на UUID из ответа `POST /books`.

---

## 5. Все эндпоинты — что отправлять

Ниже: **Method**, **Path**, нужна ли авторизация, **Body** (JSON) и ожидаемый код.

---

### Health

| # | Method | Path | Auth | Body | Ожидается |
|---|--------|------|------|------|-----------|
| 1 | GET | `/health` | Нет | — | `200`, `{"status":"ok","db":true}` |

**Swagger:** раздел `health` → Try it out → Execute.

**Postman:** `GET {{base_url}}/health`

---

### Auth (`/auth`)

| # | Method | Path | Auth | Body | Ожидается |
|---|--------|------|------|------|-----------|
| 2 | POST | `/auth/register` | Нет | см. ниже | `201` |
| 3 | POST | `/auth/login` | Нет | см. ниже | `200` + токены |
| 4 | POST | `/auth/refresh` | Нет | `{"refresh_token":"..."}` | `200` + новые токены |
| 5 | POST | `/auth/logout` | Нет | `{"refresh_token":"..."}` | `204` |

**Register (автор):**
```json
{
  "email": "author@test.com",
  "username": "author",
  "password": "password123",
  "role": "author"
}
```

**Register (читатель):**
```json
{
  "email": "reader@test.com",
  "username": "reader",
  "password": "password123",
  "role": "reader"
}
```

`role` можно опустить для читателя — по умолчанию `"reader"`. **Сменить роль после регистрации нельзя.**

**Login:**
```json
{
  "email": "author@test.com",
  "password": "password123"
}
```

**Проверка ошибок:**
- Повторный register с тем же email → `409`
- Login с неверным паролем → `401`
- `GET /users/me` после регистрации автора → `"role": "author"`
- `POST /books` с токеном **читателя** → `403`, `"Доступно только авторам"`

---

### Users (`/users`)

| # | Method | Path | Auth | Body / Params | Ожидается |
|---|--------|------|------|---------------|-----------|
| 6 | GET | `/users/by-username/{username}` | Нет | path: `author` | `200`, без email |
| 7 | GET | `/users/me` | Bearer | — | `200` |
| 8 | PATCH | `/users/me` | Bearer | `{"username":"author","display_tag":"Писатель"}` | `200` |
| 9 | PATCH | `/users/me/password` | Bearer | `{"current_password":"password123","new_password":"newpass123"}` | `204` |
| 10 | POST | `/users/me/avatar` | Bearer | — | `200`, `upload_url`, `object_key` |
| 11 | PATCH | `/users/me/avatar-key` | Bearer | query: `object_key=avatars/...` | `200` |
| 12 | GET | `/users/me/payment-profile` | Bearer | — | `404` если не создан |
| 13 | PATCH | `/users/me/payment-profile` | Bearer | см. ниже | `200` |
| 14 | GET | `/users/me/promo-codes` | Bearer (читатель) | — | `200`, активные промокоды |
| 15 | GET | `/users/me` | Bearer | — | `200`, поле `"role": "reader"` или `"author"` |

**Payment profile:**
```json
{
  "payout_requisites_encrypted": "encrypted-requisites",
  "payment_method_token": "pm_mock_123"
}
```

**Аватар (полный flow):**
1. `POST /users/me/avatar` → получить `upload_url`
2. В Postman: `PUT` на `upload_url`, Body → binary, выберите любой `.jpg`
3. `PATCH /users/me/avatar-key?object_key=<object_key из шага 1>`

---

### Books (`/books`)

| # | Method | Path | Auth | Body / Params | Ожидается |
|---|--------|------|------|---------------|-----------|
| 14 | GET | `/books` | Нет | query: `status=published`, `q=`, `limit=20` | `200` |
| 15 | GET | `/books/recommendations` | Нет | query: `limit=10` | `200`, `new` + `popular` |
| 16 | POST | `/books` | Bearer (автор) | см. ниже | `201`, `status=draft` |
| 17 | GET | `/books/{book_id}` | Нет | — | `200` |
| 18 | PATCH | `/books/{book_id}` | Bearer (автор) | `{"title":"Новое название"}` | `200` |
| 19 | POST | `/books/{book_id}/submit` | Bearer (автор) | — | `200`, `status=pending` |
| 20 | POST | `/books/{book_id}/publish` | Bearer (автор) | — | `200`, `status=published` |
| 21 | GET | `/books/{book_id}/rating` | Нет/ Bearer | — | `200`, ratings + reviews_count |
| 22 | PUT | `/books/{book_id}/rating` | Bearer | `{ "score": 8 }` | `200` |
| 20 | POST | `/books/{book_id}/cover` | Bearer (автор) | — | `200`, presigned URL |
| 21 | PATCH | `/books/{book_id}/cover-key` | Bearer (автор) | query: `object_key=...` | `200` |
| 22 | POST | `/books/{book_id}/file` | Bearer (автор) | query: `file_format=epub` | `200`, presigned URL |
| 23 | PATCH | `/books/{book_id}/file-key` | Bearer (автор) | query: `object_key=...&file_format=epub&file_size_bytes=5000` | `200` |
| 24 | GET | `/books/{book_id}/access` | Bearer | — | `200`, `can_read`, `reason` |
| 25 | GET | `/books/{book_id}/content` | Bearer | — | `200`, бинарное тело |
| 26 | GET | `/books/{book_id}/content/chunk` | Bearer | query: `offset=0&size=1024` | `200` + `Content-Range` |
| 27 | DELETE | `/books/{book_id}` | Bearer (автор) | — | `204` |
| 28 | GET | `/books/genre-tags/all` | Нет | — | `200` |
| 29 | POST | `/books/genre-tags` | Bearer | `{"name":"Фэнтези"}` | `201` |
| 30 | PUT | `/books/{book_id}/genre-tags` | Bearer (автор) | `{"genre_tag_ids":["<uuid>"]}` | `200` |
| 31 | GET | `/books/{book_id}/genre-tags` | Нет | — | `200` |
| 32 | GET | `/books/{book_id}/user-tags` | Нет | — | `200` |
| 33 | POST | `/books/{book_id}/user-tags` | Bearer | `{"name":"Уютное"}` | `201` |
| 34 | DELETE | `/books/{book_id}/user-tags/{tag_id}` | Bearer | — | `204` |

**Создание книги (автор):**
```json
{
  "title": "Моя первая книга",
  "description": "Описание для теста",
  "is_in_subscription": true,
  "subscription_payout_amount": "10.00",
  "is_for_sale": true,
  "sale_price": "199.00"
}
```

**Загрузка обложки:**
1. `POST /books/{id}/cover` → `upload_url`, `object_key` (например `covers/<book_id>.jpg`)
2. Postman: `PUT` на `upload_url`, Body → binary, любой `.jpg`
3. `PATCH /books/{id}/cover-key?object_key=covers/<book_id>.jpg`

**Загрузка файла книги:**
1. `POST /books/{id}/file?file_format=epub` → `upload_url`
2. Postman: `PUT` на `upload_url`, Body → binary, любой файл
3. `PATCH /books/{id}/file-key?object_key=books/{id}.epub&file_format=epub&file_size_bytes=5000`

**Проверка доступа к чтению:**
- Автор → `GET .../access` → `can_read: true`, `reason: "author"`
- Читатель без покупки/подписки → `can_read: false`, `reason: "purchase_or_subscription_required"`
- После покупки или подписки → `can_read: true`

> Прямое **скачивание** файла (`/download`) **отсутствует** — только чтение через `/content` и `/content/chunk`.

---

### Reviews

| # | Method | Path | Auth | Body | Ожидается |
|---|--------|------|------|------|-----------|
| 35 | GET | `/books/{book_id}/reviews` | Нет | — | `200` |
| 36 | POST | `/books/{book_id}/reviews` | Bearer | `{"rating":5,"text":"Отлично!"}` | `201` |
| 37 | PATCH | `/reviews/{review_id}` | Bearer (автор отзыва) | `{"rating":4,"text":"Хорошо"}` | `200` |
| 38 | DELETE | `/reviews/{review_id}` | Bearer (автор отзыва) | — | `204` |
| 39 | POST | `/reviews/{review_id}/promo-code` | Bearer (автор книги) | см. ниже | `201` |
| 40 | PUT | `/reviews/{review_id}/vote` | Bearer | `{ "vote": "like" }` | `200` |
| 41 | DELETE | `/reviews/{review_id}/vote` | Bearer | — | `200` |

**Выдача промокода автором (по отзыву):**
```json
{
  "discount_percent": 20,
  "expires_in_days": 30
}
```
- Только автор книги, на которую оставлен отзыв
- Получатель — автор отзыва (читатель)
- Один промокод на отзыв → повтор → `409`
- Код одноразовый, скидка на покупку **любой** книги этого автора

**Проверка:** второй отзыв тем же пользователем → `409`.

---

### Library (`/library`)

| # | Method | Path | Auth | Body | Ожидается |
|---|--------|------|------|------|-----------|
| 39 | GET | `/library/status` | Bearer | — | `200` |
| 40 | PUT | `/library/status/{book_id}` | Bearer | см. ниже | `200` |
| 41 | DELETE | `/library/status/{book_id}` | Bearer | — | `204` |
| 42 | GET | `/library/readlists` | Bearer | — | `200` |
| 43 | POST | `/library/readlists` | Bearer | см. ниже | `201` |
| 44 | GET | `/library/readlists/{readlist_id}` | Bearer | — | `200` |
| 45 | PATCH | `/library/readlists/{readlist_id}` | Bearer | `{"title":"Обновлённый список"}` | `200` |
| 46 | POST | `/library/readlists/{readlist_id}/books` | Bearer | `{"book_id":"<uuid>"}` | `201` |
| 47 | GET | `/library/readlists/{readlist_id}/books` | Bearer | — | `200` |
| 48 | DELETE | `/library/readlists/{readlist_id}/books/{book_id}` | Bearer | — | `204` |
| 49 | DELETE | `/library/readlists/{readlist_id}` | Bearer | — | `204` |

**Статус чтения:**
```json
{
  "status": "reading",
  "progress_percent": 35
}
```

Допустимые `status`: `reading`, `finished`, `wishlist`.

**Создание readlist:**
```json
{
  "title": "Хочу прочитать",
  "description": "Мой список",
  "is_public": true
}
```

---

### Subscriptions (`/subscriptions`)

| # | Method | Path | Auth | Body | Ожидается |
|---|--------|------|------|------|-----------|
| 50 | GET | `/subscriptions/plans` | Нет | — | `200`, минимум 1 план после seed |
| 51 | POST | `/subscriptions/subscribe` | Bearer (читатель) | см. ниже | `201` |
| 52 | GET | `/subscriptions/me` | Bearer | — | `200` |
| 53 | POST | `/subscriptions/me/cancel` | Bearer | — | `200`, `status=cancelled` |
| 54 | GET | `/subscriptions/me/payments` | Bearer | — | `200` |

**Subscribe (mock-оплата):**
```json
{
  "plan_id": "<uuid из GET /plans>",
  "auto_renew": true,
  "card": {
    "card_number": "4111111111111111",
    "cardholder_name": "TEST USER",
    "expiry_month": 12,
    "expiry_year": 2030,
    "cvv": "123"
  }
}
```

---

### Earnings (`/earnings`)

| # | Method | Path | Auth | Body | Ожидается |
|---|--------|------|------|------|-----------|
| 55 | POST | `/earnings/purchases/{book_id}` | Bearer (читатель) | mock card (как выше) | `201` |
| 56 | GET | `/earnings/purchases` | Bearer | — | `200` |
| 57 | POST | `/earnings/reads/{book_id}` | Bearer (читатель с подпиской) | — | `200` |
| 58 | GET | `/earnings/balance` | Bearer (автор) | — | `200` или `404` |
| 59 | GET | `/earnings/stats` | Bearer (автор) | query: `year`, `month` | `200` |
| 60 | GET | `/earnings/transactions` | Bearer (автор) | — | `200` |
| 61 | POST | `/earnings/payouts` | Bearer (автор) | `{"amount":"50.00"}` | `201` |
| 62 | GET | `/earnings/payouts` | Bearer (автор) | — | `200` |
| 63 | GET | `/earnings/promo-codes` | Bearer (автор) | — | `200`, выданные промокоды |
| 64 | GET | `/earnings/stats/books` | Bearer (автор) | query: `q`, `year`, `month` | `200`, per-book stats |

**Purchase body** — карта + опциональный `promo_code`:
```json
{
  "card_number": "4111111111111111",
  "cardholder_name": "TEST USER",
  "expiry_month": 12,
  "expiry_year": 2030,
  "cvv": "123",
  "promo_code": "ABC123XYZ"
}
```

**Purchase body** — только объект карты (без plan_id):
```json
{
  "card_number": "4111111111111111",
  "cardholder_name": "TEST USER",
  "expiry_month": 12,
  "expiry_year": 2030,
  "cvv": "123"
}
```

**Reads по подписке** — книга должна быть `published` и `is_in_subscription=true`. Повторный вызов → `{"status":"already_opened"}`.

---

## 6. Чеклист «всё проверил»

Отметьте после прохода:

- [ ] Health OK
- [ ] Register + Login (2 пользователя)
- [ ] Refresh + Logout
- [ ] Профиль, пароль, payment profile
- [ ] Создание книги, upload cover/file, submit
- [ ] SQL publish → access/content для читателя
- [ ] Подписка или покупка → чтение content
- [ ] Отзывы CRUD
- [ ] Library status + readlists
- [ ] Earnings: stats, balance, payout
- [ ] Recommendations + публичный профиль

---

## 7. Сверка с ТЗ — что реализовано

| Требование ТЗ | Статус | Как проверить |
|---------------|--------|---------------|
| Регистрация / вход (логин+пароль) | ✅ | `POST /auth/register`, `/auth/login` |
| Главная: поиск книг | ✅ | `GET /books?q=...&status=published` |
| Главная: рекомендации | ✅ (базовые) | `GET /books/recommendations` — новинки + популярные |
| Страница книги: данные, теги, отзывы | ✅ | `GET /books/{id}`, genre/user tags, reviews |
| Публичный профиль автора | ✅ | `GET /users/by-username/{username}` |
| Чтение только через сайт (не скачивание) | ✅ | `GET /books/{id}/content`, `/content/chunk` |
| Контроль доступа: подписка / покупка | ✅ | `GET /books/{id}/access` |
| Автор: CRUD книг, upload, submit | ✅ | `/books/*` |
| Автор: статистика (чтения, продажи, доход) | ✅ | `GET /earnings/stats` |
| Автор: баланс и вывод | ✅ | `/earnings/balance`, `POST /earnings/payouts` |
| Подписка: тарифы, оформление, отмена | ✅ (mock) | `/subscriptions/*` |
| Покупка отдельной книги | ✅ (mock) | `POST /earnings/purchases/{id}` |
| Личный кабинет: статусы чтения | ✅ | `PUT /library/status/{book_id}` |
| Кастомные списки (readlists) | ✅ | `/library/readlists/*` |
| Настройки: профиль, пароль, аватар | ✅ | `/users/me*` |
| Платёжный профиль (реквизиты) | ✅ | `/users/me/payment-profile` |
| Начисление автору за чтение по подписке | ✅ | `POST /earnings/reads/{book_id}` |
| Промокоды от автора по отзыву | ✅ | `POST /reviews/{id}/promo-code`, purchase с `promo_code` |
| Seed тарифа и жанров при старте | ✅ | `GET /subscriptions/plans`, `GET /books/genre-tags/all` |

### Не реализовано / вне scope MVP

| Требование | Статус | Примечание |
|------------|--------|------------|
| Модерация (publish/reject) | ⚠️ | `POST /books/{id}/publish` — автор публикует сам; админ reject нет |
| Email-верификация | ❌ | По договорённости не нужна |
| Реальные платежи | ❌ | Mock-карта всегда проходит |
| ML-персональные рекомендации | ❌ | Простые new/popular вместо ML |
| Админ: обработка payout | ❌ | Автор создаёт заявку, статус `pending` |
| Фоновые задачи (auto-renew, expiry job) | ❌ | Подписка проверяется по `expires_at` при доступе |
| Прямое скачивание файла | ❌ | Намеренно убрано — только inline-чтение |

---

## 8. Частые ошибки

| Код | Причина | Решение |
|-----|---------|---------|
| `401` | Нет или истёк токен | Login / Refresh |
| `403` | Нет прав на книгу | Купить, подписаться, или быть автором |
| `404` | Книга не опубликована | SQL `UPDATE status='published'` |
| `409` | Дубликат (email, отзыв, покупка) | Ожидаемое поведение |
| `422` | Невалидное тело | Проверьте JSON по примерам выше |

---

## 9. Автотесты

```powershell
docker compose up db -d
docker compose exec -T db psql -U aeon -d postgres -c "CREATE DATABASE aeonbiblio_test;"
# PYTEST_DATABASE_URL — см. .env.example (или задайте в .env)
python -m pytest
```

61 тест, coverage ≥ 90%.

> После последних доработок: **85 тестов**.
