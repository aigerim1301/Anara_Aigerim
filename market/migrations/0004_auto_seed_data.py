# Generated data migration to auto-populate categories and initial data on deploy

from decimal import Decimal
from django.db import migrations

CATEGORIES = [
    ("Учебники и книги", "books"),
    ("Техника и гаджеты", "tech"),
    ("Одежда и вещи", "clothes"),
    ("Спорт и хобби", "sport"),
    ("Другое", "other"),
]

USERS = [
    ("moderator", "Мария", "Модератор", "moderator"),
    ("aibek", "Айбек", "К.", "member"),
    ("alina", "Алина", "С.", "member"),
    ("timur", "Тимур", "К.", "member"),
    ("nazira", "Назира", "Б.", "member"),
]


def create_initial_data(apps, schema_editor):
    Category = apps.get_model("market", "Category")
    User = apps.get_model("market", "User")
    Listing = apps.get_model("market", "Listing")
    from django.contrib.auth.hashers import make_password

    # 1. Создаем категории
    cats = {}
    for name, slug in CATEGORIES:
        cat, _ = Category.objects.get_or_create(slug=slug, defaults={"name": name})
        cats[slug] = cat

    # 2. Создаем пользователей
    users = {}
    for username, first, last, role in USERS:
        user = User.objects.filter(username=username).first()
        if not user:
            user = User.objects.create(
                username=username,
                email=f"{username}@example.com",
                first_name=first,
                last_name=last,
                role=role,
                password=make_password("demo12345"),
                is_active=True,
            )
        users[username] = user

    # 3. Создаем администратора
    if not User.objects.filter(username="admin").exists():
        admin = User.objects.create(
            username="admin",
            email="admin@example.com",
            first_name="Админ",
            role="moderator",
            password=make_password("admin12345"),
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        users["admin"] = admin
    else:
        users["admin"] = User.objects.get(username="admin")

    # 4. Создаем базовые объявления в каталоге, если объявлений ещё нет
    if not Listing.objects.exists():
        sample_items = [
            ("Ноутбук Acer Aspire 5", "Продаю ноутбук Acer Aspire 5 в отличном состоянии. i5, 8 ГБ ОЗУ, SSD 256 ГБ. Подходит для учёбы и работы.", "tech", "like_new", "sale", Decimal("45000"), "aibek"),
            ("Учебники по экономике (3 шт.)", "Три учебника по экономике за первый курс. Ищу обмен на учебники по праву или менеджменту.", "books", "used", "exchange", None, "alina"),
            ("Куртка зимняя, размер M", "Тёплая зимняя куртка, носил один сезон. Отдам бесплатно, заберите сами из общежития.", "clothes", "used", "free", Decimal("0"), "timur"),
            ("Наушники JBL Tune 510BT", "Беспроводные наушники, работают отлично, в комплекте кабель для зарядки и чехол.", "tech", "like_new", "sale", Decimal("5000"), "nazira"),
            ("Рюкзак Xiaomi", "Вместительный рюкзак с отделением для ноутбука 15 дюймов. Небольшие следы носки.", "clothes", "used", "sale", Decimal("1800"), "aibek"),
            ("Калькулятор Casio fx-991", "Инженерный калькулятор, разрешён на экзаменах. Всё работает, батарейка новая.", "tech", "used", "sale", Decimal("2000"), "alina"),
            ("Конспекты по высшей математике", "Аккуратные рукописные конспекты за два семестра, все темы по программе колледжа. Отдам даром.", "books", "used", "free", Decimal("0"), "nazira"),
            ("Python. Карманный справочник", "Практичный справочник по Python, почти не открывал, без пометок и загнутых страниц.", "books", "like_new", "sale", Decimal("700"), "timur"),
        ]
        for title, desc, cat_slug, cond, mode, price, seller_name in sample_items:
            Listing.objects.create(
                seller=users[seller_name],
                category=cats[cat_slug],
                title=title,
                description=desc,
                condition=cond,
                mode=mode,
                price=price,
                status="published",
                search_text=f"{title} {desc}".lower(),
            )


def remove_initial_data(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0003_botmessage'),
    ]

    operations = [
        migrations.RunPython(create_initial_data, remove_initial_data),
    ]

