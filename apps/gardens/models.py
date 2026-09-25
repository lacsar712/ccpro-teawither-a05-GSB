from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone


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


class LeafReceipt(models.Model):
    """装叶中槽的鲜叶签收单。

    规则（详见 README「鲜叶签收规则」）：
    - 仅「装叶中」槽可签收；萎凋中、可下槽一律拒绝。
    - 同一槽装叶中期间，累计签收千克不得超过该槽装叶量 ``loadKg``，
      超出拒绝并回显该槽已累计签收千克。
    - 该槽若已存在萎凋批次，则单次签收千克不得超过同槽最新批次
      目标含水率百分数的数值本身（目标含水 62.00% 即单次上限 62 kg）。
    - 鲜叶千克必须为正。
    """

    trough = models.ForeignKey(
        Trough,
        on_delete=models.CASCADE,
        related_name="receipts",
        verbose_name="所属槽位",
    )
    kg = models.DecimalField(
        "鲜叶千克",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    receivedAt = models.DateTimeField("签收时刻", default=timezone.now)
    village = models.CharField("供货村名", max_length=120)
    receiver = models.CharField("签收人", max_length=80)

    class Meta:
        ordering = ["-receivedAt", "-id"]
        verbose_name = "鲜叶签收"
        verbose_name_plural = "鲜叶签收"

    def __str__(self):
        return f"{self.trough} {self.kg}kg @ {self.receivedAt:%Y-%m-%d %H:%M}"

    @classmethod
    def received_kg(cls, trough):
        """该槽装叶中期间已累计签收的鲜叶千克。"""
        result = cls.objects.filter(trough=trough).aggregate(total=Sum("kg"))
        return result["total"] or Decimal("0")

    @classmethod
    def week_start(cls, now=None):
        """本周一 00:00（当前时区）；首页合计与列表本周行共用此边界。"""
        now = now or timezone.localtime()
        return (now - timezone.timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    @classmethod
    def week_kg(cls, now=None):
        """本周（周一 00:00 起）签收千克合计；与列表本周各行求和同源。"""
        result = cls.objects.filter(
            receivedAt__gte=cls.week_start(now)
        ).aggregate(total=Sum("kg"))
        return (result["total"] or Decimal("0")).quantize(Decimal("0.01"))

    def clean(self):
        super().clean()
        errors = {}
        kg_errors = []

        if self.kg is not None and self.kg <= 0:
            kg_errors.append("鲜叶千克必须为正数。")

        if self.trough_id:
            if self.trough.status != Trough.STATUS_LOADING:
                errors["trough"] = (
                    "仅「装叶中」槽可签收鲜叶；萎凋中与可下槽槽位拒绝签收。"
                )
            else:
                # 累计装叶量约束
                already = self.__class__.received_kg(self.trough)
                if self.pk:
                    current = (
                        self.__class__.objects.filter(pk=self.pk)
                        .values_list("kg", flat=True)
                        .first()
                    )
                    if current is not None:
                        already -= current
                if self.kg is not None and already + self.kg > self.trough.loadKg:
                    kg_errors.append(
                        f"签收后累计 {already + self.kg}kg 将超过该槽装叶量 "
                        f"{self.trough.loadKg}kg；该槽已累计签收 {already}kg，"
                        f"本次至多还可签收 {self.trough.loadKg - already}kg。"
                    )

                # 与同槽最新批次目标含水联锁
                latest = self.trough.latest_batch()
                if (
                    latest is not None
                    and self.kg is not None
                    and self.kg > latest.targetMoisture
                ):
                    kg_errors.append(
                        f"该槽已有萎凋批次，单次签收不得超过最新批次目标含水率"
                        f"{latest.targetMoisture}% 的数值本身（{latest.targetMoisture}kg）。"
                    )

        if kg_errors:
            errors["kg"] = kg_errors
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # 禁止签收成功却不校验装叶量：保存前一律执行完整业务校验。
        self.full_clean()
        return super().save(*args, **kwargs)
