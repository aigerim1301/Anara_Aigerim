"""Представления CampusMarket. Все проверки прав выполняются на сервере."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import (DealRequestForm, FilterForm, ListingForm, MessageForm, ProfileForm,
                    RegisterForm, ReportForm)
from .models import Category, DealRequest, Favorite, Listing, ListingImage, Message, Report

L = Listing.Status
D = DealRequest.Status
R = Report.Status
PAGE_SIZE = 9
LIST_PAGE_SIZE = 10


class Conflict(Exception):
    """Конфликт состояния (аналог HTTP 409)."""


# ---------- помощники ----------

def moderator_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_moderator:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


def safe_next(request, fallback):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return fallback


def public_listings():
    return (Listing.objects.filter(status=L.PUBLISHED)
            .select_related("category", "seller").prefetch_related("images"))


def favorite_ids(user):
    if not user.is_authenticated:
        return set()
    return set(Favorite.objects.filter(user=user).values_list("listing_id", flat=True))


def paginate(request, qs, size=LIST_PAGE_SIZE):
    return Paginator(qs, size).get_page(request.GET.get("page"))


IMAGE_SIZE = (1200, 900)  # все фото приводятся к одному размеру 4:3


def normalize_image(uploaded):
    """Фото целиком помещается в рамку 4:3, поля заполняет размытая копия."""
    from io import BytesIO

    from django.core.files.base import ContentFile
    from PIL import Image, ImageFilter, ImageOps

    img = ImageOps.exif_transpose(Image.open(uploaded))
    if img.mode in ("RGBA", "LA", "P"):
        flat = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        flat.paste(rgba, mask=rgba.split()[-1])
        img = flat
    else:
        img = img.convert("RGB")

    canvas_w, canvas_h = IMAGE_SIZE
    background = ImageOps.fit(img, IMAGE_SIZE, method=Image.LANCZOS).filter(ImageFilter.GaussianBlur(28))
    background = Image.blend(background, Image.new("RGB", IMAGE_SIZE, (255, 255, 255)), 0.35)
    photo = ImageOps.contain(img, IMAGE_SIZE, method=Image.LANCZOS)
    background.paste(photo, ((canvas_w - photo.width) // 2, (canvas_h - photo.height) // 2))

    buffer = BytesIO()
    background.save(buffer, "JPEG", quality=88, optimize=True)
    return ContentFile(buffer.getvalue())


def save_images(listing, files):
    import uuid

    last = listing.images.aggregate(m=Max("position"))["m"]
    start = 0 if last is None else last + 1
    for offset, f in enumerate(files):
        content = normalize_image(f)
        image = ListingImage(listing=listing, position=start + offset)
        image.image.save(f"{uuid.uuid4().hex}.jpg", content, save=True)

# ---------- публичные страницы ----------

def home(request):
    categories = Category.objects.annotate(
        total=Count("listings", filter=Q(listings__status=L.PUBLISHED)))
    latest = public_listings()[:6]
    return render(request, "market/home.html", {
        "categories": categories, "latest": latest, "fav_ids": favorite_ids(request.user)})


def how_it_works(request):
    return render(request, "market/how_it_works.html")


def catalog(request):
    form = FilterForm(request.GET or None)
    form.is_valid()
    data = form.cleaned_data if form.is_bound else {}
    qs = public_listings()
    if data.get("q"):
        for word in data["q"].lower().split():
            qs = qs.filter(search_text__contains=word)
    if data.get("category"):
        qs = qs.filter(category=data["category"])
    if data.get("mode"):
        qs = qs.filter(mode=data["mode"])
    if data.get("condition"):
        qs = qs.filter(condition=data["condition"])
    if data.get("price_min") is not None:
        qs = qs.filter(price__gte=data["price_min"])
    if data.get("price_max") is not None:
        qs = qs.filter(price__lte=data["price_max"])
    sort = data.get("sort") or "new"
    ordering = {
        "new": ["-created_at"],
        "old": ["created_at"],
        "price_asc": [F("price").asc(nulls_last=True), "-created_at"],
        "price_desc": [F("price").desc(nulls_last=True), "-created_at"],
    }[sort]
    qs = qs.order_by(*ordering)
    page = paginate(request, qs, PAGE_SIZE)
    return render(request, "market/catalog.html", {
        "form": form, "page": page, "categories": Category.objects.all(),
        "fav_ids": favorite_ids(request.user), "sort": sort, "total": page.paginator.count,
        "modes": Listing.Mode.choices, "conditions": Listing.Condition.choices,
        "sorts": FilterForm.SORT_CHOICES,
        "g": request.GET,
    })


def listing_detail(request, pk):
    listing = get_object_or_404(
        Listing.objects.select_related("category", "seller").prefetch_related("images"), pk=pk)
    user = request.user
    is_owner = user.is_authenticated and listing.seller_id == user.id
    my_request = None
    if user.is_authenticated:
        my_request = listing.requests.filter(buyer=user).order_by("-created_at").first()
    public = listing.status in (L.PUBLISHED, L.RESERVED)
    if not public:
        allowed = is_owner or (user.is_authenticated and user.is_moderator) or my_request is not None
        if not allowed:
            raise Http404
    active_request = my_request if (my_request and my_request.status in DealRequest.ACTIVE) else None
    return render(request, "market/listing_detail.html", {
        "listing": listing, "images": list(listing.images.all()), "is_owner": is_owner,
        "is_fav": listing.pk in favorite_ids(user), "my_request": my_request,
        "can_request": (user.is_authenticated and not is_owner and listing.status == L.PUBLISHED
                        and active_request is None),
        "request_form": DealRequestForm(),
        "seller_count": Listing.objects.filter(seller=listing.seller, status=L.PUBLISHED).count(),
    })


# ---------- аккаунт ----------

def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Добро пожаловать в CampusMarket!")
        return redirect("home")
    return render(request, "auth/register.html", {"form": form})


@login_required
def profile(request):
    user = request.user
    return render(request, "market/profile.html", {
        "stats": {
            "listings": Listing.objects.filter(seller=user).count(),
            "favorites": Favorite.objects.filter(user=user).count(),
            "requests": DealRequest.objects.filter(Q(buyer=user) | Q(listing__seller=user)).count(),
        }})


@login_required
def profile_edit(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Профиль сохранён.")
        return redirect("profile")
    return render(request, "market/profile_edit.html", {"form": form})


@login_required
def account_delete(request):
    if request.method == "POST":
        user = request.user
        with transaction.atomic():
            Listing.objects.filter(seller=user, status=L.PUBLISHED).update(status=L.ARCHIVED)
            DealRequest.objects.filter(buyer=user, status=D.PENDING).update(status=D.CANCELLED)
            DealRequest.objects.filter(listing__seller=user, status=D.PENDING).update(status=D.REJECTED)
            user.is_active = False
            user.save(update_fields=["is_active"])
        logout(request)
        messages.success(request, "Аккаунт удалён. История ваших сделок сохранена анонимно.")
        return redirect("home")
    return render(request, "market/account_delete.html")


# ---------- объявления автора ----------

@login_required
def listing_create(request):
    if request.method == "POST":
        form = ListingForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                listing = form.save(commit=False)
                listing.seller = request.user
                listing.status = L.PUBLISHED
                listing.save()
                save_images(listing, form.cleaned_data["images"])
            messages.success(request, "Объявление опубликовано.")
            return redirect(listing)
    else:
        form = ListingForm()
    return render(request, "market/listing_form.html", {"form": form, "listing": None, "images": []})


@login_required
def listing_edit(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    if listing.seller_id != request.user.id:
        raise PermissionDenied
    if not listing.is_editable:
        messages.error(request, "Это объявление уже нельзя редактировать.")
        return redirect("my_listings")
    delete_ids = []
    if request.method == "POST":
        delete_ids = [int(x) for x in request.POST.getlist("delete_images") if x.isdigit()]
        form = ListingForm(request.POST, request.FILES, instance=listing, delete_ids=delete_ids)
        if form.is_valid():
            with transaction.atomic():
                form.save()
                listing.images.filter(pk__in=delete_ids).delete()
                save_images(listing, form.cleaned_data["images"])
            messages.success(request, "Изменения сохранены.")
            return redirect(listing)
    else:
        form = ListingForm(instance=listing)
    return render(request, "market/listing_form.html", {
        "form": form, "listing": listing, "images": listing.images.all(), "delete_ids": delete_ids})


LISTING_ACTIONS = {
    "archive": (L.PUBLISHED, L.ARCHIVED, "Объявление снято с публикации."),
    "restore": (L.ARCHIVED, L.PUBLISHED, "Объявление снова опубликовано."),
    "release": (L.RESERVED, L.PUBLISHED, "Резерв снят, объявление снова в каталоге."),
    "complete": (L.RESERVED, L.COMPLETED, "Отмечено как «передано». Остальные заявки отклонены."),
}


@login_required
@require_POST
def listing_action(request, pk, action):
    listing = get_object_or_404(Listing, pk=pk)
    if listing.seller_id != request.user.id:
        raise PermissionDenied
    if action not in LISTING_ACTIONS:
        raise Http404
    source, target, success = LISTING_ACTIONS[action]
    with transaction.atomic():
        if listing.status != source or not listing.change_status(target):
            messages.error(request, "Это действие сейчас недоступно: статус объявления изменился.")
            return redirect("my_listings")
        if action == "release":
            listing.requests.filter(status=D.ACCEPTED).update(status=D.REJECTED, updated_at=timezone.now())
        if action == "complete":
            listing.requests.filter(status=D.PENDING).update(status=D.REJECTED, updated_at=timezone.now())
    messages.success(request, success)
    return redirect(safe_next(request, "my_listings"))


@login_required
def my_listings(request):
    tab = request.GET.get("tab", "all")
    base = Listing.objects.filter(seller=request.user)
    counts = {
        "all": base.count(),
        "published": base.filter(status=L.PUBLISHED).count(),
        "reserved": base.filter(status=L.RESERVED).count(),
        "archive": base.filter(status__in=[L.ARCHIVED, L.COMPLETED, L.HIDDEN]).count(),
    }
    qs = base
    if tab == "published":
        qs = qs.filter(status=L.PUBLISHED)
    elif tab == "reserved":
        qs = qs.filter(status=L.RESERVED)
    elif tab == "archive":
        qs = qs.filter(status__in=[L.ARCHIVED, L.COMPLETED, L.HIDDEN])
    else:
        tab = "all"
    qs = (qs.select_related("category").prefetch_related("images")
          .annotate(pending=Count("requests", filter=Q(requests__status=D.PENDING))))
    return render(request, "market/my_listings.html", {
        "page": paginate(request, qs), "tab": tab, "counts": counts})


# ---------- заявки и переписка ----------

@login_required
@require_POST
def request_create(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    if listing.seller_id == request.user.id:
        messages.error(request, "Нельзя подать заявку на своё объявление.")
        return redirect(listing)
    if listing.status != L.PUBLISHED:
        messages.error(request, "На это объявление сейчас нельзя подать заявку.")
        return redirect(listing)
    form = DealRequestForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors["text"][0])
        return redirect(listing)
    if listing.requests.filter(buyer=request.user, status__in=DealRequest.ACTIVE).exists():
        messages.error(request, "Вы уже отправили заявку на это объявление.")
        return redirect(listing)
    try:
        with transaction.atomic():
            deal = DealRequest.objects.create(listing=listing, buyer=request.user, text=form.cleaned_data["text"])
            Message.objects.create(request=deal, sender=request.user, text=deal.text)
    except IntegrityError:
        messages.error(request, "Вы уже отправили заявку на это объявление.")
        return redirect(listing)
    messages.success(request, "Заявка отправлена. Продавец увидит её в своём кабинете.")
    return redirect("request_detail", pk=deal.pk)


def participant_request(request, pk):
    deal = get_object_or_404(
        DealRequest.objects.select_related("listing", "listing__seller", "buyer"), pk=pk)
    if request.user.id not in (deal.buyer_id, deal.listing.seller_id):
        raise PermissionDenied
    return deal


@login_required
def request_detail(request, pk):
    deal = participant_request(request, pk)
    if request.method == "POST":
        if deal.status not in DealRequest.ACTIVE:
            messages.error(request, "Заявка закрыта, писать сообщения больше нельзя.")
            return redirect("request_detail", pk=deal.pk)
        form = MessageForm(request.POST)
        if form.is_valid():
            Message.objects.create(request=deal, sender=request.user, text=form.cleaned_data["text"])
        else:
            messages.error(request, form.errors["text"][0])
        return redirect("request_detail", pk=deal.pk)
    is_seller = deal.listing.seller_id == request.user.id
    other = deal.buyer if is_seller else deal.listing.seller
    return render(request, "market/request_detail.html", {
        "deal": deal, "chat": deal.messages.select_related("sender"), "is_seller": is_seller,
        "other": other, "can_write": deal.status in DealRequest.ACTIVE,
        "cover": deal.listing.images.first()})


@login_required
@require_POST
def request_accept(request, pk):
    deal = get_object_or_404(DealRequest.objects.select_related("listing"), pk=pk)
    if deal.listing.seller_id != request.user.id:
        raise PermissionDenied
    now = timezone.now()
    try:
        with transaction.atomic():
            # Условный UPDATE: сработает только у одного из одновременных запросов.
            reserved = Listing.objects.filter(pk=deal.listing_id, status=L.PUBLISHED).update(
                status=L.RESERVED, updated_at=now)
            if not reserved:
                raise Conflict("Вещь уже зарезервирована или снята с публикации.")
            accepted = DealRequest.objects.filter(pk=deal.pk, status=D.PENDING).update(
                status=D.ACCEPTED, updated_at=now)
            if not accepted:
                raise Conflict("Эта заявка уже обработана.")
    except Conflict as exc:
        messages.error(request, str(exc))
    except IntegrityError:
        messages.error(request, "Для этого объявления уже есть принятая заявка.")
    else:
        messages.success(request, "Получатель выбран, вещь зарезервирована.")
    return redirect(safe_next(request, "my_requests"))


@login_required
@require_POST
def request_reject(request, pk):
    deal = get_object_or_404(DealRequest.objects.select_related("listing"), pk=pk)
    if deal.listing.seller_id != request.user.id:
        raise PermissionDenied
    if deal.status != D.PENDING or not deal.change_status(D.REJECTED):
        messages.error(request, "Эту заявку уже нельзя отклонить.")
    else:
        messages.success(request, "Заявка отклонена.")
    return redirect(safe_next(request, "my_requests"))


@login_required
@require_POST
def request_cancel(request, pk):
    deal = get_object_or_404(DealRequest.objects.select_related("listing"), pk=pk)
    if deal.buyer_id != request.user.id:
        raise PermissionDenied
    with transaction.atomic():
        was_accepted = deal.status == D.ACCEPTED
        if not deal.change_status(D.CANCELLED):
            messages.error(request, "Эту заявку уже нельзя отменить.")
            return redirect(safe_next(request, "my_requests"))
        if was_accepted:
            Listing.objects.filter(pk=deal.listing_id, status=L.RESERVED).update(
                status=L.PUBLISHED, updated_at=timezone.now())
    messages.success(request, "Заявка отменена.")
    return redirect(safe_next(request, "my_requests"))


@login_required
def my_requests(request):
    user = request.user
    tab = request.GET.get("tab", "incoming")
    mine = (DealRequest.objects.filter(Q(buyer=user) | Q(listing__seller=user))
            .select_related("listing", "listing__seller", "buyer").prefetch_related("listing__images"))
    closed = Q(status__in=[D.REJECTED, D.CANCELLED]) | Q(listing__status=L.COMPLETED)
    incoming = mine.filter(listing__seller=user, status__in=DealRequest.ACTIVE).exclude(listing__status=L.COMPLETED)
    outgoing = mine.filter(buyer=user, status__in=DealRequest.ACTIVE).exclude(listing__status=L.COMPLETED)
    archive = mine.filter(closed)
    only_listing = request.GET.get("listing")
    if only_listing and only_listing.isdigit():
        incoming = incoming.filter(listing_id=int(only_listing))
    counts = {"incoming": incoming.count(), "outgoing": outgoing.count(), "archive": archive.count()}
    qs = {"incoming": incoming, "outgoing": outgoing, "archive": archive}.get(tab)
    if qs is None:
        tab, qs = "incoming", incoming
    return render(request, "market/my_requests.html", {
        "page": paginate(request, qs), "tab": tab, "counts": counts})


@login_required
def my_messages(request):
    user = request.user
    chats = (DealRequest.objects.filter(Q(buyer=user) | Q(listing__seller=user))
             .select_related("listing", "listing__seller", "buyer").prefetch_related("listing__images")
             .annotate(last_at=Max("messages__created_at")).order_by(F("last_at").desc(nulls_last=True)))
    return render(request, "market/my_messages.html", {"page": paginate(request, chats)})


# ---------- избранное ----------

@login_required
@require_POST
def favorite_toggle(request, pk):
    listing = get_object_or_404(Listing, pk=pk, status__in=[L.PUBLISHED, L.RESERVED])
    fav, created = Favorite.objects.get_or_create(user=request.user, listing=listing)
    if not created:
        fav.delete()
    return redirect(safe_next(request, listing.get_absolute_url()))


@login_required
def favorites(request):
    items = (Listing.objects.filter(favorited_by__user=request.user, status__in=[L.PUBLISHED, L.RESERVED])
             .select_related("category").prefetch_related("images").order_by("-favorited_by__created_at"))
    return render(request, "market/favorites.html", {
        "page": paginate(request, items, PAGE_SIZE), "fav_ids": favorite_ids(request.user)})


# ---------- жалобы и модерация ----------

@login_required
def report_create(request, pk):
    listing = get_object_or_404(Listing, pk=pk, status__in=[L.PUBLISHED, L.RESERVED])
    if listing.seller_id == request.user.id:
        messages.error(request, "Нельзя пожаловаться на своё объявление.")
        return redirect(listing)
    form = ReportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                Report.objects.create(listing=listing, reporter=request.user, reason=form.cleaned_data["reason"])
        except IntegrityError:
            messages.error(request, "Вы уже отправляли жалобу на это объявление, её рассматривает модератор.")
        else:
            messages.success(request, "Спасибо! Жалоба отправлена модератору.")
        return redirect(listing)
    return render(request, "market/report_form.html", {"form": form, "listing": listing})


@login_required
def my_reports(request):
    qs = Report.objects.filter(reporter=request.user).select_related("listing")
    return render(request, "market/my_reports.html", {"page": paginate(request, qs)})


@moderator_required
def moderation_reports(request):
    tab = request.GET.get("tab", "new")
    counts = {s: Report.objects.filter(status=s).count() for s in (R.NEW, R.IN_PROGRESS, R.RESOLVED)}
    if tab not in counts:
        tab = R.NEW
    qs = (Report.objects.filter(status=tab).select_related("listing", "reporter", "resolved_by")
          .prefetch_related("listing__images"))
    return render(request, "market/moderation.html", {
        "page": paginate(request, qs), "tab": tab, "counts": counts})


@moderator_required
@require_POST
def moderation_action(request, pk):
    report = get_object_or_404(Report.objects.select_related("listing"), pk=pk)
    action = request.POST.get("action")
    reason = request.POST.get("reason", "").strip()
    now = timezone.now()
    if report.status == R.RESOLVED:
        messages.error(request, "Эта жалоба уже решена.")
    elif action == "take":
        Report.objects.filter(pk=report.pk, status=R.NEW).update(status=R.IN_PROGRESS)
        messages.success(request, "Жалоба взята в работу.")
    elif action == "hide":
        if len(reason) < 5:
            messages.error(request, "Укажите причину скрытия (не менее 5 символов).")
        else:
            with transaction.atomic():
                if report.listing.change_status(L.HIDDEN):
                    Listing.objects.filter(pk=report.listing_id).update(hide_reason=reason)
                    Report.objects.filter(listing=report.listing).exclude(status=R.RESOLVED).update(
                        status=R.RESOLVED, resolution=f"Объявление скрыто: {reason}",
                        resolved_by=request.user, resolved_at=now)
                    messages.success(request, "Объявление скрыто из каталога.")
                else:
                    messages.error(request, "Это объявление сейчас нельзя скрыть (например, оно в резерве или передано).")
    elif action == "dismiss":
        Report.objects.filter(pk=report.pk).exclude(status=R.RESOLVED).update(
            status=R.RESOLVED, resolution=reason or "Нарушений не найдено.",
            resolved_by=request.user, resolved_at=now)
        messages.success(request, "Жалоба закрыта без последствий.")
    else:
        raise Http404
    return redirect(safe_next(request, "moderation_reports"))


@moderator_required
@require_POST
def listing_unhide(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    if listing.change_status(L.PUBLISHED):
        Listing.objects.filter(pk=listing.pk).update(hide_reason="")
        messages.success(request, "Объявление возвращено в каталог.")
    else:
        messages.error(request, "Это объявление не скрыто.")
    return redirect(listing)
