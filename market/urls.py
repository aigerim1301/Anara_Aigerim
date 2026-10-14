from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("how-it-works/", views.how_it_works, name="how_it_works"),
    path("listings/", views.catalog, name="catalog"),
    path("listings/new/", views.listing_create, name="listing_create"),
    path("listings/<int:pk>/", views.listing_detail, name="listing_detail"),
    path("listings/<int:pk>/edit/", views.listing_edit, name="listing_edit"),
    path("listings/<int:pk>/archive/", views.listing_action, {"action": "archive"}, name="listing_archive"),
    path("listings/<int:pk>/restore/", views.listing_action, {"action": "restore"}, name="listing_restore"),
    path("listings/<int:pk>/release/", views.listing_action, {"action": "release"}, name="listing_release"),
    path("listings/<int:pk>/complete/", views.listing_action, {"action": "complete"}, name="listing_complete"),
    path("listings/<int:pk>/unhide/", views.listing_unhide, name="listing_unhide"),
    path("listings/<int:pk>/requests/", views.request_create, name="request_create"),
    path("listings/<int:pk>/favorite/", views.favorite_toggle, name="favorite_toggle"),
    path("listings/<int:pk>/report/", views.report_create, name="report_create"),

    path("requests/<int:pk>/", views.request_detail, name="request_detail"),
    path("requests/<int:pk>/accept/", views.request_accept, name="request_accept"),
    path("requests/<int:pk>/reject/", views.request_reject, name="request_reject"),
    path("requests/<int:pk>/cancel/", views.request_cancel, name="request_cancel"),

    path("my/listings/", views.my_listings, name="my_listings"),
    path("my/requests/", views.my_requests, name="my_requests"),
    path("my/messages/", views.my_messages, name="my_messages"),
    path("my/favorites/", views.favorites, name="favorites"),
    path("my/reports/", views.my_reports, name="my_reports"),

    path("moderation/reports/", views.moderation_reports, name="moderation_reports"),
    path("moderation/reports/<int:pk>/", views.moderation_action, name="moderation_action"),

    path("accounts/register/", views.register, name="register"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="auth/login.html",
                                                          redirect_authenticated_user=True), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("profile/delete/", views.account_delete, name="account_delete"),
]
