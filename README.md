# CampusMarket — студенческая барахолка

Семестровый проект (3 курс): площадка для продажи, обмена и бесплатной передачи учебников, техники и вещей между студентами.

**Стек:** Python 3.10+, Django 5.1+, SQLite (для разработки) / PostgreSQL, HTML + CSS + немного JavaScript.

## Запуск с нуля

```bash
# 1. Клонировать репозиторий и перейти в папку
git clone <ссылка-на-ваш-репозиторий> campusmarket
cd campusmarket

# 2. Виртуальное окружение
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS / Linux

# 3. Зависимости
pip install -r requirements.txt

# 4. Настройки
copy .env.example .env           # Windows   (macOS/Linux: cp .env.example .env)

# 5. База данных: миграции
python manage.py makemigrations market   # только если папка market/migrations пуста
python manage.py migrate

# 6. Демо-данные
python manage.py seed_demo

# 7. Запуск
python manage.py runserver
```

Открыть: http://127.0.0.1:8000/

Пересоздать демо-данные заново: `python manage.py seed_demo --reset`

## Тестовые аккаунты

| Роль | Логин | Пароль |
|---|---|---|
| Участник | `aibek`, `alina`, `timur`, `nazira` | `demo12345` |
| Модератор | `moderator` | `demo12345` |
| Администратор (и /admin/) | `admin` | `admin12345` |

Администратор назначает модераторов в панели `/admin/` (поле «Роль»). При регистрации роль выбрать нельзя.

## Тесты

```bash
python manage.py test
```

Покрыто: права доступа (чужое объявление, чужой чат, модерация), валидация (цена, 6-е фото, исполняемый файл), основной сценарий (публикация → заявка → резерв → передача), запрещённые переходы статусов, конкурирующий выбор получателя (включая ограничение на уровне БД).

## Роли и права

| Действие | Гость | Участник | Модератор |
|---|---|---|---|
| Читать каталог и объявления | да | да | да |
| Публиковать, редактировать свои объявления | нет | да | да |
| Заявки, переписка, избранное, жалобы | нет | да | да |
| Разбор жалоб, скрытие объявлений | нет | нет | да |

Все проверки выполняются на сервере (`market/views.py`), а не только скрытием кнопок.

## Статусы и бизнес-правила

Объявление: `опубликовано → резерв → передано`; из резерва можно вернуться в `опубликовано`; `архив` доступен до передачи; модератор может перевести в `скрыто`.

Заявка: `на рассмотрении → принята / отклонена / отменена`.

- Продажа: цена > 0. Даром: цена 0. Обмен: цены нет (правило закреплено и в БД через `CheckConstraint`).
- Не более одной принятой заявки на объявление: условный UNIQUE-индекс в БД + атомарный `UPDATE ... WHERE status='published'` в коде.
- Нельзя подать заявку на своё объявление; в резерве цену и режим менять нельзя.
- Фото: до 5 шт., до 5 МБ, только JPG/PNG/WebP (проверяются расширение, MIME-тип и реальное содержимое).
- Удаление аккаунта = деактивация: история сделок не ломается (внешние ключи `PROTECT`).

## ER-диаграмма

```mermaid
erDiagram
    USER ||--o{ LISTING : "продаёт (seller)"
    CATEGORY ||--o{ LISTING : "содержит"
    LISTING ||--o{ LISTING_IMAGE : "до 5 фото"
    LISTING ||--o{ DEAL_REQUEST : "получает заявки"
    USER ||--o{ DEAL_REQUEST : "подаёт (buyer)"
    DEAL_REQUEST ||--o{ MESSAGE : "переписка"
    USER ||--o{ MESSAGE : "отправляет"
    USER ||--o{ FAVORITE : ""
    LISTING ||--o{ FAVORITE : ""
    LISTING ||--o{ REPORT : "жалобы"
    USER ||--o{ REPORT : "подаёт (reporter)"

    USER { int id PK; string username; string email UK; string role; bool is_active }
    CATEGORY { int id PK; string name UK; string slug UK }
    LISTING { int id PK; int seller_id FK; int category_id FK; string title; text description; string condition; string mode; decimal price; string status; string hide_reason }
    LISTING_IMAGE { int id PK; int listing_id FK; file image; int position }
    DEAL_REQUEST { int id PK; int listing_id FK; int buyer_id FK; text text; string status }
    MESSAGE { int id PK; int request_id FK; int sender_id FK; text text; datetime created_at }
    FAVORITE { int id PK; int user_id FK; int listing_id FK }
    REPORT { int id PK; int listing_id FK; int reporter_id FK; text reason; string status; text resolution; int resolved_by_id FK }
```

Удаление: фото, сообщения и избранное удаляются вместе с родителем (`CASCADE`); объявления, заявки и жалобы защищены (`PROTECT`), потому что это история сделок.

## Маршруты

| Метод | URL | Доступ | Назначение |
|---|---|---|---|
| GET | `/`, `/how-it-works/` | все | главная, справка |
| GET | `/listings/` | все | каталог: `q`, `category`, `mode`, `condition`, `price_min`, `price_max`, `sort`, `page` |
| GET | `/listings/<id>/` | все* | карточка (*скрытые/снятые видят автор и модератор) |
| GET/POST | `/listings/new/`, `/listings/<id>/edit/` | автор | создание, редактирование |
| POST | `/listings/<id>/archive/`, `restore/`, `release/`, `complete/` | автор | смена статуса |
| POST | `/listings/<id>/requests/` | участник | подать заявку |
| POST | `/listings/<id>/favorite/` | участник | добавить/убрать из избранного |
| GET/POST | `/listings/<id>/report/` | участник | пожаловаться |
| POST | `/listings/<id>/unhide/` | модератор | вернуть скрытое объявление |
| GET/POST | `/requests/<id>/` | продавец и заявитель | переписка |
| POST | `/requests/<id>/accept/`, `reject/` | продавец | выбрать получателя / отклонить |
| POST | `/requests/<id>/cancel/` | заявитель | отменить |
| GET | `/my/listings/`, `/my/requests/`, `/my/messages/`, `/my/favorites/`, `/my/reports/` | вошедший | кабинет |
| GET/POST | `/moderation/reports/`, `/moderation/reports/<id>/` | модератор | жалобы и решения |
| GET/POST | `/accounts/register/`, `/accounts/login/`, `/accounts/logout/` | | вход и выход |
| GET/POST | `/profile/`, `/profile/edit/`, `/profile/delete/` | вошедший | профиль |

Ошибки: 403 (нет прав), 404 (нет объекта), понятные сообщения на формах; конфликты состояния (например, вещь уже зарезервирована) показываются пользователю текстом.

## Часовой пояс и деньги

Время хранится в UTC (`USE_TZ=True`), на сайте показывается в поясе из `TIME_ZONE` (по умолчанию `Asia/Bishkek`), он указан в подвале. Цены — `DecimalField`, валюта — сом.

## Известные ограничения

- Реальные платежи, доставка, геолокация и push-уведомления не реализованы (не входят в обязательный объём).
- Объявление в резерве нельзя скрыть модератором: сначала нужно снять резерв.
- Файлы удалённых фотографий остаются на диске в `media/`.
- Переписка работает на обычных HTTP-запросах: новые сообщения видны после обновления страницы.

## Журнал разработки

**Неделя 1:** выбор темы, ТЗ, дизайн-макеты, ER-диаграмма. **Недели 2–5:** модели, вход, роли, объявления. **Недели 6–8:** каталог, заявки, резерв, переписка, избранное, жалобы, модерация. **Недели 9–12:** дизайн и адаптивность, тесты, демо-данные, README.
