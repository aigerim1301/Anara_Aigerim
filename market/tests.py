"""Автотесты CampusMarket. Запуск: python manage.py test"""
import io
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Category, DealRequest, Listing, Message, Report, User

TEMP_MEDIA = tempfile.mkdtemp()
L = Listing.Status
D = DealRequest.Status


def png(name="a.png"):
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class BaseCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cat = Category.objects.create(name="Учебники", slug="books")
        mk = lambda name, **kw: User.objects.create_user(name, f"{name}@example.com", "pass12345", **kw)
        cls.seller = mk("seller", first_name="Продавец")
        cls.buyer = mk("buyer", first_name="Покупатель")
        cls.buyer2 = mk("buyer2", first_name="Второй")
        cls.stranger = mk("stranger", first_name="Чужой")
        cls.moderator = mk("mod", role="moderator")

    def make_listing(self, **kw):
        data = dict(seller=self.seller, category=self.cat, title="Учебник по экономике",
                    description="Хороший учебник, без пометок.", condition="used",
                    mode="sale", price=300, status=L.PUBLISHED)
        data.update(kw)
        return Listing.objects.create(**data)

    def make_request(self, listing, buyer, status=D.PENDING):
        return DealRequest.objects.create(listing=listing, buyer=buyer, text="Хочу забрать", status=status)

    def listing_data(self, **kw):
        data = {"title": "Учебник по экономике", "category": self.cat.pk, "mode": "sale", "price": "300",
                "condition": "used", "description": "Хороший учебник, без пометок и загнутых страниц."}
        data.update(kw)
        return data


class ListingTests(BaseCase):
    def test_create_listing_and_find_in_catalog(self):
        """Основной сценарий: опубликовать, найти фильтром без учёта регистра."""
        self.client.force_login(self.seller)
        resp = self.client.post(reverse("listing_create"), self.listing_data(images=[png()]))
        self.assertEqual(resp.status_code, 302)
        listing = Listing.objects.get()
        self.assertEqual(listing.status, L.PUBLISHED)
        self.assertEqual(listing.images.count(), 1)
        resp = self.client.get(reverse("catalog"), {"q": "УЧЕБНИК", "mode": "sale", "price_max": "500"})
        self.assertContains(resp, "Учебник по экономике")
        resp = self.client.get(reverse("catalog"), {"q": "ноутбук"})
        self.assertNotContains(resp, "Учебник по экономике")

    def test_negative_and_zero_price_for_sale_rejected(self):
        self.client.force_login(self.seller)
        for bad in ("-5", "0", ""):
            resp = self.client.post(reverse("listing_create"), self.listing_data(price=bad))
            self.assertEqual(resp.status_code, 200)
            self.assertIn("price", resp.context["form"].errors)
        self.assertEqual(Listing.objects.count(), 0)

    def test_price_normalized_for_free_and_exchange(self):
        self.client.force_login(self.seller)
        self.client.post(reverse("listing_create"), self.listing_data(mode="free", price="500"))
        self.client.post(reverse("listing_create"), self.listing_data(mode="exchange", price="500", title="Обмен учебника"))
        self.assertEqual(Listing.objects.get(mode="free").price, 0)
        self.assertIsNone(Listing.objects.get(mode="exchange").price)

    def test_sixth_photo_rejected(self):
        self.client.force_login(self.seller)
        files = [png(f"{i}.png") for i in range(6)]
        resp = self.client.post(reverse("listing_create"), self.listing_data(images=files))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("images", resp.context["form"].errors)
        self.assertEqual(Listing.objects.count(), 0)

    def test_executable_file_rejected(self):
        self.client.force_login(self.seller)
        exe = SimpleUploadedFile("virus.exe", b"MZ\x90\x00", content_type="application/x-msdownload")
        resp = self.client.post(reverse("listing_create"), self.listing_data(images=[exe]))
        self.assertIn("images", resp.context["form"].errors)
        fake = SimpleUploadedFile("fake.png", b"not really an image", content_type="image/png")
        resp = self.client.post(reverse("listing_create"), self.listing_data(images=[fake]))
        self.assertIn("images", resp.context["form"].errors)
        self.assertEqual(Listing.objects.count(), 0)

    def test_database_constraint_price_matches_mode(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_listing(mode="free", price=100)

    def test_foreign_user_cannot_edit(self):
        listing = self.make_listing()
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(reverse("listing_edit", args=[listing.pk])).status_code, 403)
        resp = self.client.post(reverse("listing_edit", args=[listing.pk]), self.listing_data(title="Взлом"))
        self.assertEqual(resp.status_code, 403)
        listing.refresh_from_db()
        self.assertNotEqual(listing.title, "Взлом")

    def test_price_and_mode_locked_while_reserved(self):
        listing = self.make_listing(status=L.RESERVED)
        self.client.force_login(self.seller)
        self.client.post(reverse("listing_edit", args=[listing.pk]),
                         self.listing_data(price="1", mode="free", title="Новое название"))
        listing.refresh_from_db()
        self.assertEqual(listing.title, "Новое название")
        self.assertEqual(listing.price, 300)
        self.assertEqual(listing.mode, "sale")


class DealFlowTests(BaseCase):
    def test_full_successful_flow(self):
        listing = self.make_listing()
        self.client.force_login(self.buyer)
        resp = self.client.post(reverse("request_create", args=[listing.pk]), {"text": "Хочу забрать"})
        deal = DealRequest.objects.get()
        self.assertRedirects(resp, reverse("request_detail", args=[deal.pk]))
        self.assertEqual(deal.status, D.PENDING)

        self.client.force_login(self.seller)
        self.client.post(reverse("request_accept", args=[deal.pk]))
        listing.refresh_from_db(); deal.refresh_from_db()
        self.assertEqual((listing.status, deal.status), (L.RESERVED, D.ACCEPTED))

        self.client.post(reverse("listing_complete", args=[listing.pk]))
        listing.refresh_from_db()
        self.assertEqual(listing.status, L.COMPLETED)
        self.assertNotContains(self.client.get(reverse("catalog")), "Учебник по экономике")

    def test_cannot_request_own_listing(self):
        listing = self.make_listing()
        self.client.force_login(self.seller)
        self.client.post(reverse("request_create", args=[listing.pk]), {"text": "Сам себе"})
        self.assertEqual(DealRequest.objects.count(), 0)

    def test_duplicate_request_blocked(self):
        listing = self.make_listing()
        self.client.force_login(self.buyer)
        for _ in range(2):
            self.client.post(reverse("request_create", args=[listing.pk]), {"text": "Хочу забрать"})
        self.assertEqual(DealRequest.objects.count(), 1)

    def test_second_accept_does_not_create_second_reservation(self):
        """Конкурирующие запросы: принять можно только одного получателя."""
        listing = self.make_listing()
        d1 = self.make_request(listing, self.buyer)
        d2 = self.make_request(listing, self.buyer2)
        self.client.force_login(self.seller)
        self.client.post(reverse("request_accept", args=[d1.pk]))
        self.client.post(reverse("request_accept", args=[d2.pk]))
        listing.refresh_from_db(); d1.refresh_from_db(); d2.refresh_from_db()
        self.assertEqual(listing.status, L.RESERVED)
        self.assertEqual(d1.status, D.ACCEPTED)
        self.assertEqual(d2.status, D.PENDING)
        self.assertEqual(DealRequest.objects.filter(listing=listing, status=D.ACCEPTED).count(), 1)

    def test_database_blocks_two_accepted_requests(self):
        listing = self.make_listing(status=L.RESERVED)
        self.make_request(listing, self.buyer, status=D.ACCEPTED)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_request(listing, self.buyer2, status=D.ACCEPTED)

    def test_forbidden_status_transition(self):
        listing = self.make_listing(status=L.COMPLETED)
        self.assertFalse(listing.change_status(L.PUBLISHED))
        self.client.force_login(self.seller)
        self.client.post(reverse("listing_restore", args=[listing.pk]))
        self.client.post(reverse("listing_release", args=[listing.pk]))
        listing.refresh_from_db()
        self.assertEqual(listing.status, L.COMPLETED)

    def test_release_reservation_returns_to_catalog(self):
        listing = self.make_listing()
        deal = self.make_request(listing, self.buyer)
        self.client.force_login(self.seller)
        self.client.post(reverse("request_accept", args=[deal.pk]))
        self.client.post(reverse("listing_release", args=[listing.pk]))
        listing.refresh_from_db(); deal.refresh_from_db()
        self.assertEqual((listing.status, deal.status), (L.PUBLISHED, D.REJECTED))

    def test_complete_rejects_other_requests(self):
        listing = self.make_listing()
        d1 = self.make_request(listing, self.buyer)
        d2 = self.make_request(listing, self.buyer2)
        self.client.force_login(self.seller)
        self.client.post(reverse("request_accept", args=[d1.pk]))
        self.client.post(reverse("listing_complete", args=[listing.pk]))
        d2.refresh_from_db()
        self.assertEqual(d2.status, D.REJECTED)


class PermissionTests(BaseCase):
    def setUp(self):
        self.listing = self.make_listing()
        self.deal = self.make_request(self.listing, self.buyer, status=D.ACCEPTED)

    def test_stranger_cannot_read_or_write_chat(self):
        self.client.force_login(self.stranger)
        url = reverse("request_detail", args=[self.deal.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"text": "Привет"}).status_code, 403)
        self.assertEqual(Message.objects.count(), 0)

    def test_participants_can_chat(self):
        url = reverse("request_detail", args=[self.deal.pk])
        for user in (self.buyer, self.seller):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 200)
            self.client.post(url, {"text": f"Сообщение от {user.username}"})
        self.assertEqual(Message.objects.count(), 2)

    def test_chat_closed_after_cancel(self):
        self.deal.status = D.CANCELLED
        self.deal.save()
        self.client.force_login(self.buyer)
        self.client.post(reverse("request_detail", args=[self.deal.pk]), {"text": "Ещё одно"})
        self.assertEqual(Message.objects.count(), 0)

    def test_only_seller_can_accept(self):
        listing = self.make_listing(title="Другое")
        deal = self.make_request(listing, self.buyer)
        for user in (self.buyer, self.stranger):
            self.client.force_login(user)
            self.assertEqual(self.client.post(reverse("request_accept", args=[deal.pk])).status_code, 403)
        listing.refresh_from_db()
        self.assertEqual(listing.status, L.PUBLISHED)

    def test_anonymous_redirected_to_login(self):
        for name in ("my_listings", "my_requests", "favorites", "listing_create"):
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 302)
            self.assertIn(reverse("login"), resp["Location"])


class ModerationTests(BaseCase):
    def test_member_cannot_open_moderation(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(reverse("moderation_reports")).status_code, 403)

    def test_moderator_hides_listing_from_catalog(self):
        listing = self.make_listing()
        report = Report.objects.create(listing=listing, reporter=self.buyer, reason="Спам в описании объявления")
        self.client.force_login(self.moderator)
        self.client.post(reverse("moderation_action", args=[report.pk]), {"action": "hide", "reason": "Спам в описании"})
        listing.refresh_from_db(); report.refresh_from_db()
        self.assertEqual(listing.status, L.HIDDEN)
        self.assertEqual(report.status, Report.Status.RESOLVED)
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("catalog")), "Учебник по экономике")
        self.assertEqual(self.client.get(reverse("listing_detail", args=[listing.pk])).status_code, 404)

    def test_hide_requires_reason_and_member_cannot_hide(self):
        listing = self.make_listing()
        report = Report.objects.create(listing=listing, reporter=self.buyer, reason="Спам в описании объявления")
        self.client.force_login(self.moderator)
        self.client.post(reverse("moderation_action", args=[report.pk]), {"action": "hide", "reason": ""})
        listing.refresh_from_db()
        self.assertEqual(listing.status, L.PUBLISHED)
        self.client.force_login(self.stranger)
        resp = self.client.post(reverse("moderation_action", args=[report.pk]), {"action": "hide", "reason": "Спам в описании"})
        self.assertEqual(resp.status_code, 403)

    def test_report_validation_and_duplicates(self):
        listing = self.make_listing()
        self.client.force_login(self.buyer)
        url = reverse("report_create", args=[listing.pk])
        self.client.post(url, {"reason": "коротко"})
        self.assertEqual(Report.objects.count(), 0)
        self.client.post(url, {"reason": "Подробное описание нарушения"})
        self.client.post(url, {"reason": "Подробное описание нарушения"})
        self.assertEqual(Report.objects.count(), 1)


class AccountTests(BaseCase):
    def test_register_validates_and_logs_in(self):
        data = {"username": "newbie", "email": "newbie@example.com", "first_name": "Новичок",
                "password1": "Strong-pass-2026", "password2": "Strong-pass-2026"}
        resp = self.client.post(reverse("register"), {**data, "password2": "other"})
        self.assertEqual(User.objects.filter(username="newbie").count(), 0)
        self.assertEqual(resp.status_code, 200)
        self.client.post(reverse("register"), data)
        user = User.objects.get(username="newbie")
        self.assertEqual(user.role, User.Role.MEMBER)
        self.assertFalse(user.is_staff)
        self.assertEqual(self.client.get(reverse("profile")).status_code, 200)

    def test_favorite_toggle(self):
        listing = self.make_listing()
        self.client.force_login(self.buyer)
        url = reverse("favorite_toggle", args=[listing.pk])
        self.client.post(url)
        self.assertEqual(self.buyer.favorites.count(), 1)
        self.client.post(url)
        self.assertEqual(self.buyer.favorites.count(), 0)

    def test_deleted_account_keeps_history(self):
        listing = self.make_listing(status=L.COMPLETED)
        self.make_request(listing, self.buyer, status=D.ACCEPTED)
        self.client.force_login(self.seller)
        self.client.post(reverse("account_delete"))
        self.seller.refresh_from_db()
        self.assertFalse(self.seller.is_active)
        self.assertEqual(DealRequest.objects.count(), 1)
        self.assertEqual(self.seller.display_name, "Удалённый пользователь")
