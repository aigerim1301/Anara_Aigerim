import os
from decimal import Decimal

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import Category, DealRequest, Listing, Message, Report, User

MAX_IMAGES = 5
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 МБ
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "first_name")
        labels = {"username": "Логин", "email": "Email", "first_name": "Имя"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["email"].required = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Пользователь с таким email уже зарегистрирован.")
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "bio")
        labels = {"first_name": "Имя", "last_name": "Фамилия", "bio": "О себе"}
        widgets = {"bio": forms.Textarea(attrs={"rows": 3})}


def validate_image(f):
    """Проверка размера, расширения, MIME-типа и реального содержимого картинки."""
    from PIL import Image

    if f.size > MAX_IMAGE_SIZE:
        raise ValidationError(f"Файл «{f.name}» больше 5 МБ.")
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Файл «{f.name}»: допустимы только JPG, PNG и WebP.")
    content_type = getattr(f, "content_type", None)
    if content_type and content_type not in ALLOWED_MIME:
        raise ValidationError(f"Файл «{f.name}»: недопустимый тип файла.")
    try:
        img = Image.open(f)
        img.verify()
        fmt = img.format
    except Exception:
        raise ValidationError(f"Файл «{f.name}» не является изображением.")
    finally:
        f.seek(0)
    if fmt not in ALLOWED_FORMATS:
        raise ValidationError(f"Файл «{f.name}»: допустимы только JPG, PNG и WebP.")
    return f


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        return [validate_image(f) for f in files if f]


class ListingForm(forms.ModelForm):
    images = MultipleImageField(required=False, label="Фотографии")

    class Meta:
        model = Listing
        fields = ("title", "category", "mode", "price", "condition", "description")
        labels = {"title": "Заголовок", "category": "Категория", "mode": "Режим",
                  "price": "Цена, сом", "condition": "Состояние", "description": "Описание"}
        widgets = {"description": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, delete_ids=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.delete_ids = delete_ids or []
        self.fields["category"].queryset = Category.objects.all()
        self.fields["category"].empty_label = "Выберите категорию"
        self.fields["price"].required = False
        self.fields["title"].min_length = 3
        # В резерве цену и режим менять нельзя
        if self.instance.pk and self.instance.status == Listing.Status.RESERVED:
            self.fields["price"].disabled = True
            self.fields["mode"].disabled = True

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 3:
            raise ValidationError("Заголовок должен быть не короче 3 символов.")
        return title

    def clean_description(self):
        text = self.cleaned_data["description"].strip()
        if len(text) < 10:
            raise ValidationError("Опишите вещь подробнее (не менее 10 символов).")
        return text

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")
        price = cleaned.get("price")
        if "mode" in self.errors or "price" in self.errors:
            return cleaned
        if price is not None and price < 0:
            self.add_error("price", "Цена не может быть отрицательной.")
        elif mode == Listing.Mode.SALE:
            if price is None or price <= 0:
                self.add_error("price", "Для продажи укажите цену больше нуля.")
        elif mode == Listing.Mode.FREE:
            cleaned["price"] = Decimal("0")
        elif mode == Listing.Mode.EXCHANGE:
            cleaned["price"] = None
        # Не больше 5 фото всего (старые за вычетом удаляемых + новые)
        new_files = cleaned.get("images") or []
        existing = 0
        if self.instance.pk:
            existing = self.instance.images.exclude(pk__in=self.delete_ids).count()
        if existing + len(new_files) > MAX_IMAGES:
            self.add_error("images", "Можно загрузить не более 5 фотографий.")
        return cleaned

    def _post_clean(self):
        super()._post_clean()

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.price = self.cleaned_data.get("price")
        if commit:
            obj.save()
        return obj


class DealRequestForm(forms.ModelForm):
    class Meta:
        model = DealRequest
        fields = ("text",)
        labels = {"text": "Сообщение продавцу"}
        widgets = {"text": forms.Textarea(attrs={"rows": 3, "placeholder": "Здравствуйте! Хотел бы забрать вашу вещь. Когда удобно встретиться?"})}

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if len(text) < 3:
            raise ValidationError("Напишите продавцу хотя бы пару слов.")
        return text


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ("text",)

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if not text:
            raise ValidationError("Сообщение не может быть пустым.")
        return text


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ("reason",)
        labels = {"reason": "Причина жалобы"}
        widgets = {"reason": forms.Textarea(attrs={"rows": 4, "placeholder": "Что не так с этим объявлением?"})}

    def clean_reason(self):
        text = self.cleaned_data["reason"].strip()
        if len(text) < 10:
            raise ValidationError("Опишите причину подробнее (не менее 10 символов).")
        return text


class FilterForm(forms.Form):
    SORT_CHOICES = [("new", "По дате (сначала новые)"), ("old", "По дате (сначала старые)"),
                    ("price_asc", "Цена: по возрастанию"), ("price_desc", "Цена: по убыванию")]
    q = forms.CharField(required=False, max_length=100)
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False)
    mode = forms.ChoiceField(choices=Listing.Mode.choices, required=False)
    condition = forms.ChoiceField(choices=Listing.Condition.choices, required=False)
    price_min = forms.DecimalField(required=False, min_value=Decimal("0"), max_digits=10, decimal_places=2)
    price_max = forms.DecimalField(required=False, min_value=Decimal("0"), max_digits=10, decimal_places=2)
    sort = forms.ChoiceField(choices=SORT_CHOICES, required=False)

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get("price_min"), cleaned.get("price_max")
        if low is not None and high is not None and low > high:
            self.add_error("price_max", "Максимальная цена меньше минимальной.")
        return cleaned
