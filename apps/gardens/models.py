from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


class Garden(models.Model):
    name = models.CharField("茶园名称", max_length=120)
    altitudeBand = models.CharField("海拔带", max_length=60)
    notes = models.TextField("备注", blank=True, default="")

    class Meta:
        ordering = ["name"]
        verbose_name = "茶园"
        verbose_name_plural = "茶园"

    def __str__(self):
        return self.name


class Trough(models.Model):
    STATUS_LOADING = "loading"
    STATUS_WITHERING = "withering"
    STATUS_READY = "ready"
    STATUS_CHOICES = [
        (STATUS_LOADING, "装叶中"),
        (STATUS_WITHERING, "萎凋中"),
        (STATUS_READY, "可下槽"),
    ]

    garden = models.ForeignKey(
        Garden,
        on_delete=models.CASCADE,
        related_name="troughs",
        verbose_name="茶园",
    )
    troughCode = models.CharField("槽位编号", max_length=40)
    cultivar = models.CharField("茶树品种", max_length=80)
    loadKg = models.DecimalField("装叶量(kg)", max_digits=10, decimal_places=2)
    status = models.CharField(
        "状态",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_LOADING,
    )

    class Meta:
        ordering = ["garden__name", "troughCode"]
        verbose_name = "萎凋槽"
        verbose_name_plural = "萎凋槽"
        constraints = [
            models.UniqueConstraint(
                fields=["garden", "troughCode"],
                name="uniq_trough_code_per_garden",
            ),
        ]

    def __str__(self):
        return f"{self.garden.name}-{self.troughCode}"

    def latest_batch(self):
        return self.batches.order_by("-startedAt", "-id").first()

    def clean(self):
        super().clean()
        if self.status != self.STATUS_READY:
            return
        latest = None
        if self.pk:
            latest = (
                WitherBatch.objects.filter(trough_id=self.pk)
                .order_by("-startedAt", "-id")
                .first()
            )
        if latest is None or latest.actualMoisture is None or latest.actualMoisture > 40:
            raise ValidationError(
                {
                    "status": "无法设为可下槽：最新萎凋批次的实测含水率为空或高于 40%。"
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class WitherBatch(models.Model):
    trough = models.ForeignKey(
        Trough,
        on_delete=models.CASCADE,
        related_name="batches",
        verbose_name="萎凋槽",
    )
    startedAt = models.DateTimeField("开始时间")
    targetMoisture = models.DecimalField(
        "目标含水率(%)", max_digits=5, decimal_places=2
    )
    actualMoisture = models.DecimalField(
        "实测含水率(%)",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    rollGrade = models.CharField("揉捻等级", max_length=40)

    class Meta:
        ordering = ["-startedAt", "-id"]
        verbose_name = "萎凋批次"
        verbose_name_plural = "萎凋批次"

    def __str__(self):
        return f"{self.trough} @ {self.startedAt:%Y-%m-%d %H:%M}"


class LeafIntake(models.Model):
    """鲜叶签收：仅「装叶中」槽位可签收，累计受装叶量约束。"""

    trough = models.ForeignKey(
        Trough,
        on_delete=models.CASCADE,
        related_name="intakes",
        verbose_name="所属槽位",
    )
    leafKg = models.DecimalField("鲜叶千克(kg)", max_digits=10, decimal_places=2)
    receivedAt = models.DateTimeField("签收时刻")
    supplierVillage = models.CharField("供货村名", max_length=120)
    receiver = models.CharField("签收人", max_length=80)
    isReversed = models.BooleanField("已冲销", default=False)
    reversedAt = models.DateTimeField("冲销时刻", null=True, blank=True)
    reversedBy = models.CharField("冲销人", max_length=80, blank=True, default="")

    class Meta:
        ordering = ["-receivedAt", "-id"]
        verbose_name = "鲜叶签收"
        verbose_name_plural = "鲜叶签收"

    def __str__(self):
        return f"{self.trough} 签收 {self.leafKg}kg @ {self.receivedAt:%Y-%m-%d %H:%M}"

    @staticmethod
    def accumulated_kg(trough, exclude_pk=None):
        """该槽未冲销签收的累计千克（不含 exclude_pk 指定记录）。"""
        qs = LeafIntake.objects.filter(trough=trough, isReversed=False)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.aggregate(total=models.Sum("leafKg"))["total"] or Decimal("0")

    def clean(self):
        super().clean()
        errors = {}
        if self.leafKg is not None and self.leafKg <= 0:
            errors.setdefault("leafKg", []).append("鲜叶千克必须为正数。")
        if self.isReversed:
            # 冲销记录不再参与装叶量/状态联锁校验
            if errors:
                raise ValidationError(errors)
            return
        if self.trough_id:
            trough = self.trough
            if trough.status != Trough.STATUS_LOADING:
                errors.setdefault("trough", []).append(
                    "仅「装叶中」的槽位可签收鲜叶，「萎凋中」与「可下槽」拒绝签收。"
                )
            elif self.leafKg is not None and self.leafKg > 0:
                accumulated = LeafIntake.accumulated_kg(trough, exclude_pk=self.pk)
                if accumulated + self.leafKg > trough.loadKg:
                    errors.setdefault("leafKg", []).append(
                        f"累计签收超出装叶量：该槽已累计 {accumulated} kg，"
                        f"装叶量上限 {trough.loadKg} kg，本次 {self.leafKg} kg 被拒绝。"
                    )
                latest = trough.latest_batch()
                if latest is not None and self.leafKg > latest.targetMoisture:
                    errors.setdefault("leafKg", []).append(
                        f"单次签收超出约定上限：该槽最新批次目标含水率为 "
                        f"{latest.targetMoisture}%，按约定单次签收不得超过 "
                        f"{latest.targetMoisture} kg，本次 {self.leafKg} kg 被拒绝。"
                    )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
