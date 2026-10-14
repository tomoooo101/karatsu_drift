from django.contrib import admin

from .models import CostRecord, Like, Post, Vehicle, VehicleModel


@admin.register(VehicleModel)
class VehicleModelAdmin(admin.ModelAdmin):
    list_display = ("maker", "model_name", "model_year", "engine_displacement_cc", "fuel_type")
    search_fields = ("maker", "model_name")
    list_filter = ("maker", "fuel_type")


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("nickname", "owner", "model", "is_active", "share_for_stats")
    search_fields = ("owner__email", "model__maker", "model__model_name", "nickname")
    list_filter = ("is_active", "share_for_stats")


@admin.register(CostRecord)
class CostRecordAdmin(admin.ModelAdmin):
    list_display = ("occurred_on", "vehicle", "category", "amount")
    list_filter = ("category", "occurred_on")
    date_hierarchy = "occurred_on"


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("created_at", "author", "model_name", "is_public")
    search_fields = ("author__email", "model_name", "text")
    list_filter = ("is_public", "created_at")


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "post")
    search_fields = ("user__email", "post__text")
