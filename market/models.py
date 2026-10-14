"""Модели CampusMarket.

Правило по удалению: исторические записи (объявления, заявки, жалобы) защищены
через PROTECT. Аккаунт пользователя не удаляется, а деактивируется.
"""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        MEMBER = "member", "Участник"
        MODERATOR = "moderator", "Модератор"

    email = models.EmailField("Email", unique=True)
    role = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.MEMBER)
    bio = models.CharField("О себе", max_length=300, blank=True)

    @property
    def is_moderator(self) -> bool:
        return self.is_active and (self.role == self.Role.MODERATOR or self.is_staff or self.is_superuser)

    @property
    def display_name(self) -> str:
        if not self.is_active:
            return "Удалённый пользователь"
        return self.get_full_name() or self.username

    def __str__(self):
        return self.display_name


class Category(models.Model):
    name = models.CharField("Название", max_length=60, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name


class Listing(models.Model):
    class Condition(models.TextChoices):
        NEW = "new", "Новое"
        LIKE_NEW = "like_new", "Как новое"
        USED = "used", "Б/у"

    class Mode(models.TextChoices):
        SALE = "sale", "Продажа"
        EXCHANGE = "exchange", "Обмен"
        FREE = "free", "Даром"

    class Status(models.TextChoices):
        PUBLISHED = "published", "Опубликовано"
        RESERVED = "reserved", "Резерв"
        COMPLETED = "completed", "Передано"
        ARCHIVED = "archived", "В архиве"
        HIDDEN = "hidden", "Скрыто модератором"

    # Допустимые переходы статусов. Всё остальное сервер отклоняет.
    TRANSITIONS = {
        Status.PUBLISHED: {Status.RESERVED, Status.ARCHIVED, Status.HIDDEN},
        Status.RESERVED: {Status.PUBLISHED, Status.COMPLETED},
        Status.ARCHIVED: {Status.PUBLISHED, Status.HIDDEN},
        Status.COMPLETED: set(),
        Status.HIDDEN: {Status.PUBLISHED},
    }
    EDITABLE_STATUSES = (Status.PUBLISHED, Status.RESERVED, Status.ARCHIVED)

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="listings")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="listings", verbose_name="Категория")
    title = models.CharField("Заголовок", max_length=120)
    description = models.TextField("Описание", max_length=3000)
    condition = models.CharField("Состояние", max_length=20, choices=Condition.choices, default=Condition.USED)
    mode = models.CharField("Режим", max_length=20, choices=Mode.choices, default=Mode.SALE)
    price = models.DecimalField("Цена, сом", max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.PUBLISHED)
    hide_reason = models.CharField("Причина скрытия", max_length=300, blank=True)
    # Нижний регистр заголовка+описания: так поиск работает без учёта регистра и в SQLite для кириллицы.
    search_text = models.TextField(editable=False, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Объявление"
        verbose_name_plural = "Объявления"
        indexes = [
            models.Index(fields=["status", "-created_at"], name="lst_status_created_idx"),
            models.Index(fields=["status", "price"], name="lst_status_price_idx"),
            models.Index(fields=["mode"], name="lst_mode_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(mode="sale", price__gt=0)
                    | Q(mode="free", price=0)
                    | Q(mode="exchange", price__isnull=True)
                ),
                name="listing_price_matches_mode",
            ),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.search_text = f"{self.title} {self.description}".lower()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("listing_detail", args=[self.pk])

    @property
    def cover(self):
        images = list(self.images.all())
        return images[0] if images else None

    @property
    def price_display(self) -> str:
        if self.mode == self.Mode.FREE:
            return "Бесплатно"
        if self.mode == self.Mode.EXCHANGE:
            return "Обмен"
        text = f"{Decimal(self.price).quantize(Decimal('0.01')):,.2f}".replace(",", " ")
        if text.endswith(".00"):
            text = text[:-3]
        return f"{text} сом"

    @property
    def is_editable(self) -> bool:
        return self.status in self.EDITABLE_STATUSES

    def change_status(self, new_status) -> bool:
        """Атомарная смена статуса (сравнить-и-заменить в одном UPDATE).

        Если два запроса пришли одновременно, UPDATE сработает только у одного.
        """
        if new_status not in self.TRANSITIONS.get(self.status, set()):
            return False
        updated = Listing.objects.filter(pk=self.pk, status=self.status).update(
            status=new_status, updated_at=timezone.now()
        )
        if updated:
            self.status = new_status
        return bool(updated)


class ListingImage(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="listings/%Y/%m/")
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]


class DealRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На рассмотрении"
        ACCEPTED = "accepted", "Принята"
        REJECTED = "rejected", "Отклонена"
        CANCELLED = "cancelled", "Отменена"

    TRANSITIONS = {
        Status.PENDING: {Status.ACCEPTED, Status.REJECTED, Status.CANCELLED},
        Status.ACCEPTED: {Status.REJECTED, Status.CANCELLED},
        Status.REJECTED: set(),
        Status.CANCELLED: set(),
    }
    ACTIVE = (Status.PENDING, Status.ACCEPTED)

    listing = models.ForeignKey(Listing, on_delete=models.PROTECT, related_name="requests")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requests_sent")
    text = models.TextField("Сообщение", max_length=1000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Одна активная заявка от покупателя на объявление.
            models.UniqueConstraint(
                fields=["listing", "buyer"],
                condition=Q(status__in=["pending", "accepted"]),
                name="uniq_active_request_per_buyer",
            ),
            # Не больше одной принятой заявки на объявление (защита на уровне БД).
            models.UniqueConstraint(
                fields=["listing"],
                condition=Q(status="accepted"),
                name="uniq_one_accepted_per_listing",
            ),
        ]

    def __str__(self):
        return f"Заявка #{self.pk} на «{self.listing}»"

    def change_status(self, new_status) -> bool:
        if new_status not in self.TRANSITIONS.get(self.status, set()):
            return False
        updated = DealRequest.objects.filter(pk=self.pk, status=self.status).update(
            status=new_status, updated_at=timezone.now()
        )
        if updated:
            self.status = new_status
        return bool(updated)


class Message(models.Model):
    request = models.ForeignKey(DealRequest, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    text = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["request", "created_at"], name="msg_request_created_idx")]


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "listing"], name="uniq_favorite")]


class Report(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новая"
        IN_PROGRESS = "in_progress", "В работе"
        RESOLVED = "resolved", "Решена"

    listing = models.ForeignKey(Listing, on_delete=models.PROTECT, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reports_sent")
    reason = models.TextField("Причина", max_length=500)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    resolution = models.TextField("Решение", blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reports_resolved"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "reporter"],
                condition=~Q(status="resolved"),
                name="uniq_open_report_per_user",
            ),
        ]
