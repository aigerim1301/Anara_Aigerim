"""Наполнение демонстрационными данными: python manage.py seed_demo [--reset]

Все данные и картинки вымышленные (картинки рисуются программой).
"""
import io
import textwrap

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from market.models import (Category, DealRequest, Favorite, Listing, ListingImage, Message,
                           Report, User)

PASSWORD = "demo12345"
ADMIN_PASSWORD = "admin12345"

CATEGORIES = [("Учебники и книги", "books"), ("Техника и гаджеты", "tech"), ("Одежда и вещи", "clothes"),
              ("Спорт и хобби", "sport"), ("Другое", "other")]
COLORS = {"books": (245, 158, 11), "tech": (37, 99, 235), "clothes": (16, 185, 129),
          "sport": (239, 68, 68), "other": (107, 114, 128)}

USERS = [  # username, имя, фамилия, роль
    ("moderator", "Мария", "Модератор", "moderator"),
    ("aibek", "Айбек", "К.", "member"),
    ("alina", "Алина", "С.", "member"),
    ("timur", "Тимур", "К.", "member"),
    ("nazira", "Назира", "Б.", "member"),
]

P, R, C, A = "published", "reserved", "completed", "archived"
# (заголовок, описание, категория, состояние, режим, цена, продавец, статус)
LISTINGS = [
    ("Ноутбук Acer Aspire 5", "Продаю ноутбук Acer Aspire 5 в отличном состоянии. i5, 8 ГБ ОЗУ, SSD 256 ГБ. Подходит для учёбы и работы.", "tech", "like_new", "sale", 45000, "aibek", P),
    ("Учебники по экономике (3 шт.)", "Три учебника по экономике за первый курс. Ищу обмен на учебники по праву или менеджменту.", "books", "used", "exchange", None, "alina", P),
    ("Куртка зимняя, размер M", "Тёплая зимняя куртка, носил один сезон. Отдам бесплатно, заберите сами из общежития.", "clothes", "used", "free", 0, "timur", P),
    ("Наушники JBL Tune 510BT", "Беспроводные наушники, работают отлично, в комплекте кабель для зарядки и чехол.", "tech", "like_new", "sale", 5000, "nazira", R),
    ("Рюкзак Xiaomi", "Вместительный рюкзак с отделением для ноутбука 15 дюймов. Небольшие следы носки.", "clothes", "used", "sale", 1800, "aibek", P),
    ("Калькулятор Casio fx-991", "Инженерный калькулятор, разрешён на экзаменах. Всё работает, батарейка новая.", "tech", "used", "sale", 2000, "alina", P),
    ("Конспекты по высшей математике", "Аккуратные рукописные конспекты за два семестра, все темы по программе колледжа. Отдам даром.", "books", "used", "free", 0, "nazira", P),
    ("Python. Карманный справочник", "Практичный справочник по Python, почти не открывал, без пометок и загнутых страниц.", "books", "like_new", "sale", 700, "timur", P),
    ("Горный велосипед 26 дюймов", "Велосипед на ходу, недавно менял цепь и тормозные колодки. Подойдёт для города и парка.", "sport", "used", "sale", 12000, "aibek", P),
    ("Гантели 2 × 5 кг", "Пара гантелей по 5 кг. Меняю на коврик для йоги или скакалку.", "sport", "used", "exchange", None, "alina", P),
    ("Настольная лампа", "Светодиодная лампа с регулировкой яркости, новая в коробке, подарили дубль.", "other", "new", "sale", 900, "nazira", P),
    ("Монитор Samsung 24 дюйма", "Full HD монитор, без битых пикселей. Есть кабель HDMI и подставка.", "tech", "used", "sale", 8500, "timur", R),
    ("Худи чёрное, размер L", "Чёрное худи на флисе, надевал пару раз, подошло бы тем, кто любит свободный крой.", "clothes", "like_new", "sale", 1500, "aibek", P),
    ("Учебник по базам данных", "Учебник по реляционным базам данных и SQL с разобранными примерами.", "books", "used", "free", 0, "timur", C),
    ("Электронная книга", "Читалка с подсветкой, в комплекте чехол. Меняю на беспроводную мышь или клавиатуру.", "tech", "used", "exchange", None, "nazira", P),
    ("Ролики, размер 38", "Раздвижные ролики 36–39 размеров, колёса почти новые.", "sport", "used", "sale", 2500, "alina", A),
    ("Набор чертёжных принадлежностей", "Новый набор: линейка, угольники, циркуль. Отдам бесплатно первому, кто напишет.", "other", "new", "free", 0, "aibek", P),
    ("Беспроводная мышь Logitech", "Мышь работает от одной батарейки, в комплекте USB-приёмник.", "tech", "like_new", "sale", 1200, "timur", P),
    ("Шахматы деревянные", "Деревянные шахматы с доской, фигуры тяжёлые, всё на месте. Обменяю на настольную игру.", "other", "used", "exchange", None, "nazira", P),
    ("Физика, Савельев", "Учебник по общей физике в хорошем состоянии, внутри есть пара карандашных пометок.", "books", "used", "sale", 400, "alina", P),
]

# (№ объявления с 1, покупатель, текст, статус, сообщения [(кто, текст)])
REQUESTS = [
    (4, "aibek", "Здравствуйте! Хотел бы приобрести наушники. Когда сможете передать?", "accepted",
     [("nazira", "Привет! Завтра после пар у главного входа подойдёт?"), ("aibek", "Да, отлично, буду в 16:00.")]),
    (12, "alina", "Добрый день! Монитор ещё актуален? Могу забрать на этой неделе.", "accepted",
     [("timur", "Да, актуален. Давайте в четверг."), ("alina", "Договорились, спасибо!")]),
    (12, "nazira", "Здравствуйте, можно мне монитор?", "pending", []),
    (14, "nazira", "Привет! Очень нужен учебник к семестру.", "accepted", [("timur", "Забирай, он у меня с собой."), ("nazira", "Спасибо огромное!")]),
    (14, "aibek", "Можно получить учебник?", "rejected", []),
    (1, "alina", "Здравствуйте! Ноутбук ещё продаётся? Можно посмотреть вживую?", "pending", [("aibek", "Здравствуйте, да, продаётся.")]),
    (1, "timur", "Добрый день, возможен небольшой торг?", "pending", []),
    (3, "aibek", "Здравствуйте! Куртка как раз мой размер, можно её забрать?", "pending", []),
    (2, "nazira", "Привет! Могу предложить обмен на конспекты и справочник.", "cancelled", []),
    (7, "timur", "Здравствуйте! Конспекты ещё у вас?", "pending", []),
]


def make_image(title, key, variant):
    """Рисует простую картинку-заглушку (без внешних файлов)."""
    from PIL import Image, ImageDraw, ImageFont

    w, h = 800, 600
    base = COLORS[key]
    shift = variant * 25
    color = tuple(min(255, c + shift) for c in base)
    img = Image.new("RGB", (w, h), color)
    draw = ImageDraw.Draw(img)
    draw.ellipse((-120, -120, 380, 380), fill=tuple(min(255, c + 30) for c in color))
    draw.ellipse((520, 340, 980, 800), fill=tuple(max(0, c - 30) for c in color))
    draw.rounded_rectangle((250, 170, 550, 430), radius=40, fill=(255, 255, 255), outline=(255, 255, 255))
    draw.rounded_rectangle((280, 200, 520, 340), radius=20, fill=tuple(max(0, c - 20) for c in color))
    font = None
    for path in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "arialbd.ttf", "arial.ttf",
                 "/Library/Fonts/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                 "C:/Windows/Fonts/arialbd.ttf"):
        try:
            font = ImageFont.truetype(path, 38)
            break
        except OSError:
            continue
    if font:
        lines = textwrap.wrap(title, 22)[:2]
        y = 470
        for line in lines:
            box = draw.textbbox((0, 0), line, font=font)
            draw.text(((w - (box[2] - box[0])) / 2, y), line, fill=(255, 255, 255), font=font)
            y += 50
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    return buf.getvalue()


class Command(BaseCommand):
    help = "Загружает демонстрационные данные (5 пользователей, 5 категорий, 20 объявлений, 10 заявок)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Удалить прежние демо-данные и создать заново")

    @transaction.atomic
    def handle(self, *args, **opts):
        if User.objects.filter(username="aibek").exists():
            if not opts["reset"]:
                self.stdout.write(self.style.WARNING("Демо-данные уже загружены. Для пересоздания: --reset"))
                return
            Message.objects.all().delete()
            Report.objects.all().delete()
            DealRequest.objects.all().delete()
            Favorite.objects.all().delete()
            ListingImage.objects.all().delete()
            Listing.objects.all().delete()
            Category.objects.all().delete()
            User.objects.filter(username__in=[u[0] for u in USERS] + ["admin"]).delete()

        cats = {slug: Category.objects.create(name=name, slug=slug) for name, slug in CATEGORIES}

        users = {}
        for username, first, last, role in USERS:
            users[username] = User.objects.create_user(
                username=username, email=f"{username}@example.com", password=PASSWORD,
                first_name=first, last_name=last, role=role)
        admin = User.objects.create_superuser("admin", "admin@example.com", ADMIN_PASSWORD,
                                              first_name="Админ", role="moderator")
        users["admin"] = admin

        listings = []
        for i, (title, desc, cat, cond, mode, price, seller, status) in enumerate(LISTINGS, start=1):
            listing = Listing.objects.create(
                seller=users[seller], category=cats[cat], title=title, description=desc,
                condition=cond, mode=mode, price=price, status=status)
            for pos in range(1 + i % 3):
                data = make_image(title, cat, pos)
                ListingImage.objects.create(
                    listing=listing, position=pos,
                    image=ContentFile(data, name=f"demo_{i}_{pos}.jpg"))
            listings.append(listing)

        for number, buyer, text, status, chat in REQUESTS:
            listing = listings[number - 1]
            deal = DealRequest.objects.create(listing=listing, buyer=users[buyer], text=text, status=status)
            Message.objects.create(request=deal, sender=users[buyer], text=text)
            for sender, msg in chat:
                Message.objects.create(request=deal, sender=users[sender], text=msg)

        for username, number in [("aibek", 2), ("aibek", 3), ("alina", 1), ("timur", 4), ("nazira", 9)]:
            Favorite.objects.create(user=users[username], listing=listings[number - 1])

        Report.objects.create(listing=listings[4], reporter=users["alina"],
                              reason="Подозрительно низкая цена и странное описание, прошу проверить.")
        Report.objects.create(listing=listings[17], reporter=users["nazira"],
                              reason="Фото не соответствует описанию товара.", status="in_progress")

        self.stdout.write(self.style.SUCCESS("Готово!"))
        self.stdout.write(f"Участники: aibek, alina, timur, nazira / пароль: {PASSWORD}")
        self.stdout.write(f"Модератор: moderator / пароль: {PASSWORD}")
        self.stdout.write(f"Администратор: admin / пароль: {ADMIN_PASSWORD}")
