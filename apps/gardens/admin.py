from django.contrib import admin

from .models import Garden, LeafIntake, Trough, WitherBatch


@admin.register(Garden)
class GardenAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "altitudeBand")
    search_fields = ("name", "altitudeBand")


@admin.register(Trough)
class TroughAdmin(admin.ModelAdmin):
    list_display = ("id", "garden", "troughCode", "cultivar", "loadKg", "status")
    list_filter = ("status", "garden")
    search_fields = ("troughCode", "cultivar")


@admin.register(WitherBatch)
class WitherBatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "trough",
        "startedAt",
        "targetMoisture",
        "actualMoisture",
        "rollGrade",
    )
    list_filter = ("rollGrade",)


@admin.register(LeafIntake)
class LeafIntakeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "trough",
        "leafKg",
        "receivedAt",
        "supplierVillage",
        "receiver",
        "isReversed",
        "reversedAt",
        "reversedBy",
    )
    list_filter = ("isReversed", "supplierVillage")
    search_fields = ("supplierVillage", "receiver")
