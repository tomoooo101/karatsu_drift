from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from app import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("api/session/", views.session_status, name="session"),
    path("api/register/", views.register, name="register"),
    path("api/login/", views.login_view, name="login"),
    path("api/logout/", views.logout_view, name="logout"),
    path("api/bootstrap/", views.bootstrap, name="bootstrap"),
    path("api/profile/", views.profile, name="profile"),
    path("api/profile/photo/", views.profile_photo, name="profile-photo"),
    path("api/account/delete/", views.account_delete, name="account-delete"),
    path("api/vehicles/", views.vehicle_create, name="vehicle-create"),
    path("api/vehicles/<uuid:vehicle_id>/delete/", views.vehicle_delete, name="vehicle-delete"),
    path("api/vehicles/<uuid:vehicle_id>/photo/", views.vehicle_photo, name="vehicle-photo"),
    path("api/vehicles/<uuid:vehicle_id>/share/", views.vehicle_share, name="vehicle-share"),
    path("api/costs/", views.cost_create, name="cost-create"),
    path("api/costs/<uuid:record_id>/update/", views.cost_update, name="cost-update"),
    path("api/costs/<uuid:record_id>/delete/", views.cost_delete, name="cost-delete"),
    path("api/cars/search/", views.car_search, name="car-search"),
    path("api/posts/feed/", views.post_feed, name="post-feed"),
    path("api/posts/", views.post_create, name="post-create"),
    path("api/posts/<uuid:post_id>/delete/", views.post_delete, name="post-delete"),
    path("api/posts/<uuid:post_id>/like/", views.like_toggle, name="like-toggle"),
    path("api/posts/<uuid:post_id>/unlike/", views.unlike, name="unlike"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
