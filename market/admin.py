from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Category, DealRequest, Favorite, Listing, ListingImage, Message, Report, User


@admin.register(User)
class CampusUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Роль на площадке", {"fields": ("role", "bio")}),)
    list_display = ("username", "email", "role", "is_active", "is_staff")
    list_filter = UserAdmin.list_filter + ("role",)


class ImageInline(admin.TabularInline):
    model = ListingImage
    extra = 0


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "seller", "category", "mode", "price", "status", "created_at")
    list_filter = ("status", "mode", "category")
    search_fields = ("title", "description")
    inlines = [ImageInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}


@admin.register(DealRequest)
class DealRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "buyer", "status", "created_at")
    list_filter = ("status",)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "reporter", "status", "created_at")
    list_filter = ("status",)


admin.site.register(Message)
admin.site.register(Favorite)
