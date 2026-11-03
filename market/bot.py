"""Логика чат-бота CampusBot — консультанта по каталогу CampusMarket."""
import re
from decimal import Decimal
from urllib.parse import quote_plus

from django.db.models import Count, Q
from django.utils.html import escape

from .models import Category, Listing


def get_welcome_message(user) -> str:
    name = escape(user.first_name or user.username)
    return (
        f"Привет, <b>{name}</b>! 👋 Я <b>CampusBot</b> — ваш персональный консультант по каталогу студенческой барахолки.<br><br>"
        "<b>Чем я могу помочь прямо в диалоге:</b><br>"
        "• 🔍 <b>Поиск товаров:</b> напишите, например, <i>«учебник»</i>, <i>«ноутбук»</i> или <i>«куртка»</i><br>"
        "• 🎁 <b>Бесплатные вещи:</b> напишите <i>«бесплатно»</i> или <i>«даром»</i><br>"
        "• 🔄 <b>Обмен:</b> напишите <i>«обмен»</i><br>"
        "• 💰 <b>Поиск по бюджету:</b> напишите <i>«до 500 сом»</i> или <i>«дешевле 1000»</i><br>"
        "• 📁 <b>Категории:</b> напишите <i>«категории»</i> для обзора разделов<br>"
        "• ℹ️ <b>Справка:</b> напишите <i>«как купить»</i>, <i>«как продать»</i> или <i>«безопасность»</i><br><br>"
        "Или просто выберите быстрый вопрос кнопками ниже! 👇"
    )


def _format_listing_item(item: Listing) -> str:
    url = item.get_absolute_url()
    title = escape(item.title)
    cat_name = escape(item.category.name)
    seller_name = escape(item.seller.display_name)
    price_str = escape(item.price_display)
    cond_str = escape(item.get_condition_display())
    return (
        f"• 📌 <a href=\"{url}\"><b>{title}</b></a> — <b>{price_str}</b> ({cond_str})<br>"
        f"&nbsp;&nbsp;&nbsp;<small class=\"muted\">Категория: {cat_name} · Продавец: {seller_name}</small>"
    )


def generate_bot_response(user, prompt: str) -> str:
    raw = (prompt or "").strip()
    if not raw:
        return "Напишите мне что-нибудь, и я с радостью помогу найти вещи в каталоге! 😊"

    text = raw.lower()
    tokens = re.findall(r"[\w]+", text)

    # 1. Приветствие / Старт
    greetings = {"привет", "здравствуй", "здравствуйте", "салам", "хай", "hello", "hi", "start", "старт"}
    if any(w in greetings for w in tokens) and len(tokens) <= 3:
        return get_welcome_message(user)

    # 2. Помощь / Меню
    help_words = {"помощь", "помоги", "help", "меню", "инструкция", "возможности"}
    if any(w in help_words for w in tokens) or text in ("что ты умеешь", "что умеешь", "?"):
        return get_welcome_message(user)

    # 3. Как купить / Как забрать
    if "как купить" in text or "как забрать" in text or "как заказать" in text or "хочу купить" in text:
        return (
            "🛒 <b>Как купить или забрать вещь на CampusMarket:</b><br><br>"
            "1. Найдите понравившуюся вещь в <a href=\"/listings/\">каталоге</a>.<br>"
            "2. Нажмите кнопку <b>«Хочу забрать»</b> на странице объявления.<br>"
            "3. Напишите продавцу сообщение, чтобы договориться об удобном времени и месте.<br>"
            "4. В разделе <b>«Сообщения»</b> отслеживайте статус: когда продавец выберет вас, вещь перейдёт в статус <i>Резерв</i>.<br>"
            "5. Встретьтесь в кампусе, осмотрите вещь и завершите сделку!"
        )

    # 4. Как продать / Подать объявление
    if "как продать" in text or "подать объявление" in text or "как выложить" in text or "создать объявление" in text:
        return (
            "📢 <b>Как подать объявление:</b><br><br>"
            "1. Перейдите по кнопке <b>«Подать объявление»</b> вверху сайта или по ссылке: "
            "<a href=\"/listings/new/\">Создать объявление</a>.<br>"
            "2. Выберите категорию и режим сделки (<i>Продажа</i>, <i>Обмен</i> или <i>Даром</i>).<br>"
            "3. Укажите цену (если продажа), состояние вещи и добавьте понятное описание.<br>"
            "4. Прикрепите до 5 качественных фотографий (до 5 МБ каждая).<br>"
            "5. Нажмите <b>«Опубликовать»</b> — объявление сразу появится в каталоге!"
        )

    # 5. Безопасность и правила
    if any(w in text for w in ["безопасн", "правил", "мошенник", "гаранти"]):
        return (
            "🛡️ <b>Правила безопасности на студенческой барахолке:</b><br><br>"
            "• Встречайтесь лично только в светлых и людных местах кампуса (холл главного корпуса, библиотека, студенческое кафе).<br>"
            "• Никому не переводите предоплату заранее — отдавайте деньги только после осмотра вещи.<br>"
            "• Проверяйте технику и учебники на месте.<br>"
            "• Если заметили подозрительное объявление, нажмите кнопку <b>«Пожаловаться»</b> на его карточке, и модераторы примут меры."
        )

    # 6. Бесплатные вещи (Даром)
    if any(w in text for w in ["бесплатн", "даром", "халяв", "free"]):
        free_items = (
            Listing.objects.filter(mode=Listing.Mode.FREE, status=Listing.Status.PUBLISHED)
            .select_related("category", "seller")
            .order_by("-created_at")[:5]
        )
        if free_items.exists():
            rows = [_format_listing_item(it) for it in free_items]
            return (
                "🎁 <b>Свежие бесплатные вещи («Даром»):</b><br><br>"
                + "<br>".join(rows)
                + "<br><br>👉 <a href=\"/listings/?mode=free\">Смотреть все бесплатные вещи в каталоге →</a>"
            )
        return (
            "🎁 В данный момент бесплатных объявлений нет, но студенты часто отдают вещи даром! "
            "Загляните в раздел <a href=\"/listings/?mode=free\">Бесплатно в каталоге</a> чуть позже."
        )

    # 7. Обмен
    if any(w in text for w in ["обмен", "бартер", "exchange"]):
        exchange_items = (
            Listing.objects.filter(mode=Listing.Mode.EXCHANGE, status=Listing.Status.PUBLISHED)
            .select_related("category", "seller")
            .order_by("-created_at")[:5]
        )
        if exchange_items.exists():
            rows = [_format_listing_item(it) for it in exchange_items]
            return (
                "🔄 <b>Вещи для обмена в каталоге:</b><br><br>"
                + "<br>".join(rows)
                + "<br><br>👉 <a href=\"/listings/?mode=exchange\">Смотреть все предложения обмена →</a>"
            )
        return (
            "🔄 Предложений обмена сейчас нет. Вы можете опубликовать своё предложение: "
            "<a href=\"/listings/new/\">Подать объявление на обмен</a>."
        )

    # 8. Поиск по бюджету ("до 500", "дешевле 1000", "до 300 сом")
    price_match = re.search(r"(?:до|дешевле|менее|не дороже)\s*(\d+)", text)
    if price_match:
        try:
            max_price = Decimal(price_match.group(1))
            items = (
                Listing.objects.filter(
                    status=Listing.Status.PUBLISHED,
                    mode=Listing.Mode.SALE,
                    price__lte=max_price,
                )
                .select_related("category", "seller")
                .order_by("-created_at")[:5]
            )
            if items.exists():
                rows = [_format_listing_item(it) for it in items]
                return (
                    f"💰 <b>Товары с ценой до {max_price} сом:</b><br><br>"
                    + "<br>".join(rows)
                    + f"<br><br>👉 <a href=\"/listings/?price_max={max_price}&mode=sale\">Все товары до {max_price} сом в каталоге →</a>"
                )
            return (
                f"💰 К сожалению, в продаже пока нет товаров дешевле {max_price} сом. "
                f"Попробуйте проверить <a href=\"/listings/?mode=free\">бесплатные вещи</a> или увеличить бюджет."
            )
        except Exception:
            pass

    # 9. Список категорий
    if any(w in text for w in ["категори", "раздел", "каталог"]):
        cats = (
            Category.objects.annotate(
                cnt=Count("listings", filter=Q(listings__status=Listing.Status.PUBLISHED))
            )
            .order_by("name")
        )
        if cats.exists():
            rows = [
                f"• 📁 <a href=\"/listings/?category={c.pk}\"><b>{escape(c.name)}</b></a> ({c.cnt} объявлений)"
                for c in cats
            ]
            return (
                "📁 <b>Категории товаров в каталоге CampusMarket:</b><br><br>"
                + "<br>".join(rows)
                + "<br><br>Напишите название интересующей категории или перейдите в <a href=\"/listings/\">полный каталог</a>."
            )

    # 10. Поиск по конкретной категории (проверяем, совпадает ли с существующими категориями)
    for cat in Category.objects.all():
        cat_lower = cat.name.lower()
        if cat_lower in text or cat.slug.lower() in text or (len(cat_lower) > 4 and cat_lower[:-1] in text):
            cat_items = (
                Listing.objects.filter(category=cat, status=Listing.Status.PUBLISHED)
                .select_related("category", "seller")
                .order_by("-created_at")[:5]
            )
            if cat_items.exists():
                rows = [_format_listing_item(it) for it in cat_items]
                return (
                    f"📂 <b>Свежие объявления в категории «{escape(cat.name)}»:</b><br><br>"
                    + "<br>".join(rows)
                    + f"<br><br>👉 <a href=\"/listings/?category={cat.pk}\">Смотреть все товары категории «{escape(cat.name)}» →</a>"
                )
            return (
                f"В категории «{escape(cat.name)}» сейчас нет активных объявлений. "
                f"Вы можете стать первым: <a href=\"/listings/new/\">Подать объявление</a>."
            )

    # 11. Общий поиск по ключевым словам
    # Удаляем слова-паразиты и вопросительные связки
    stop_words = {
        "найди", "найти", "ищу", "посоветуй", "покажи", "показать", "есть", "ли",
        "хочу", "купить", "пожалуйста", "где", "мне", "нужен", "нужна", "нужно",
        "вещь", "вещи", "товар", "товары", "по", "в", "на", "с", "и", "для", "подскажи"
    }
    keywords = [w for w in tokens if w not in stop_words and len(w) >= 2]
    search_query = " ".join(keywords) if keywords else raw

    # Поиск по фразе
    search_q = (
        Q(search_text__icontains=search_query)
        | Q(title__icontains=search_query)
        | Q(description__icontains=search_query)
        | Q(category__name__icontains=search_query)
    )
    items = (
        Listing.objects.filter(status=Listing.Status.PUBLISHED)
        .filter(search_q)
        .select_related("category", "seller")
        .order_by("-created_at")[:5]
    )

    # Если по всей фразе не нашли, попробуем по отдельным словам
    if not items.exists() and len(keywords) > 1:
        word_q = Q()
        for kw in keywords:
            word_q |= Q(search_text__icontains=kw) | Q(title__icontains=kw)
        items = (
            Listing.objects.filter(status=Listing.Status.PUBLISHED)
            .filter(word_q)
            .select_related("category", "seller")
            .order_by("-created_at")[:5]
        )

    if items.exists():
        rows = [_format_listing_item(it) for it in items]
        q_enc = quote_plus(search_query)
        return (
            f"🔍 <b>Вот что нашлось по запросу «{escape(search_query)}»:</b><br><br>"
            + "<br>".join(rows)
            + f"<br><br>👉 <a href=\"/listings/?q={q_enc}\">Смотреть все результаты в каталоге →</a>"
        )

    # 12. Если ничего не найдено — вежливый ответ с рекомендациями
    return (
        f"По запросу <i>«{escape(raw)}»</i> подходящих объявлений не найдено. 🔍<br><br>"
        "<b>Попробуйте:</b><br>"
        "• Написать название проще (например: <i>«учебник»</i>, <i>«ноутбук»</i>, <i>«калькулятор»</i>)<br>"
        "• Написать <i>«бесплатно»</i>, чтобы посмотреть подарки<br>"
        "• Написать <i>«категории»</i> для выбора раздела<br>"
        "• Или открыть <a href=\"/listings/\">общий каталог объявлений</a>"
    )
