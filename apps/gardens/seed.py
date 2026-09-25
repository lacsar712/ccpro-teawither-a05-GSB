from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Garden, LeafReceipt, Trough, WitherBatch


def ensure_seed_data():
    """Idempotent seed: users + sample gardens/troughs/batches."""
    User = get_user_model()

    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", "admin@teawither.local", "123456")

    if not User.objects.filter(username="witherer").exists():
        User.objects.create_user("witherer", "witherer@teawither.local", "123456")

    if Garden.objects.exists():
        return

    g1 = Garden.objects.create(
        name="云雾岭一号园",
        altitudeBand="800-1000m",
        notes="向阳坡，晨雾较重",
    )
    g2 = Garden.objects.create(
        name="竹影台二号园",
        altitudeBand="600-800m",
        notes="背风缓坡",
    )

    t1 = Trough.objects.create(
        garden=g1,
        troughCode="A-01",
        cultivar="福鼎大白",
        loadKg=Decimal("120.50"),
        status=Trough.STATUS_WITHERING,
    )
    t2 = Trough.objects.create(
        garden=g1,
        troughCode="A-02",
        cultivar="铁观音",
        loadKg=Decimal("95.00"),
        status=Trough.STATUS_LOADING,
    )
    t3 = Trough.objects.create(
        garden=g2,
        troughCode="B-01",
        cultivar="黄金芽",
        loadKg=Decimal("88.25"),
        status=Trough.STATUS_WITHERING,
    )

    now = timezone.now()
    WitherBatch.objects.create(
        trough=t1,
        startedAt=now - timezone.timedelta(hours=18),
        targetMoisture=Decimal("38.00"),
        actualMoisture=Decimal("37.50"),
        rollGrade="一级",
    )
    WitherBatch.objects.create(
        trough=t2,
        startedAt=now - timezone.timedelta(hours=2),
        targetMoisture=Decimal("40.00"),
        actualMoisture=None,
        rollGrade="待评",
    )
    WitherBatch.objects.create(
        trough=t3,
        startedAt=now - timezone.timedelta(hours=30),
        targetMoisture=Decimal("36.00"),
        actualMoisture=Decimal("42.00"),
        rollGrade="二级",
    )

    # Ready trough with valid moisture
    t4 = Trough.objects.create(
        garden=g2,
        troughCode="B-02",
        cultivar="龙井43",
        loadKg=Decimal("110.00"),
        status=Trough.STATUS_WITHERING,
    )
    WitherBatch.objects.create(
        trough=t4,
        startedAt=now - timezone.timedelta(hours=24),
        targetMoisture=Decimal("35.00"),
        actualMoisture=Decimal("34.80"),
        rollGrade="特级",
    )
    t4.status = Trough.STATUS_READY
    t4.save()

    # 装叶中槽 + 一笔恰好等于目标含水限值(40kg)的签收：
    # 再签收 >40kg 会被「目标含水联锁」拒绝，>55kg 还会超装叶量。
    LeafReceipt.objects.create(
        trough=t2,
        kg=Decimal("40.00"),
        receivedAt=now - timezone.timedelta(hours=1),
        village="青岭村",
        receiver="witherer",
    )

    # 装叶中槽：已累计签收 96kg，装叶量 100kg，
    # 再签任意 >4kg 的一笔即超装叶量，被拒绝并回显已累计 96kg。
    t5 = Trough.objects.create(
        garden=g1,
        troughCode="A-03",
        cultivar="福鼎大白",
        loadKg=Decimal("100.00"),
        status=Trough.STATUS_LOADING,
    )
    LeafReceipt.objects.create(
        trough=t5,
        kg=Decimal("96.00"),
        receivedAt=now - timezone.timedelta(minutes=40),
        village="云雾村",
        receiver="witherer",
    )
