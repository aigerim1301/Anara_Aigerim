from django import template

register = template.Library()

STATUS_CLASSES = {
    "published": "badge-green", "reserved": "badge-red", "completed": "badge-gray",
    "archived": "badge-gray", "hidden": "badge-red",
    "pending": "badge-orange", "accepted": "badge-green", "rejected": "badge-gray", "cancelled": "badge-gray",
    "new": "badge-red", "in_progress": "badge-orange", "resolved": "badge-green",
}
MODE_CLASSES = {"sale": "badge-blue", "exchange": "badge-orange", "free": "badge-green"}


@register.filter
def badge(status):
    return STATUS_CLASSES.get(status, "badge-gray")


@register.filter
def mode_badge(mode):
    return MODE_CLASSES.get(mode, "badge-blue")


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """Меняет параметры в текущей строке запроса (нужно для пагинации с фильтрами)."""
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        query[key] = value
    return query.urlencode()
