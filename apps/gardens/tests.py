from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Garden, LeafIntake, Trough, WitherBatch


def _make_intake(trough, kg, **kwargs):
    defaults = {
        "receivedAt": timezone.now(),
        "supplierVillage": "云雾村",
        "receiver": "witherer",
    }
    defaults.update(kwargs)
    return LeafIntake(trough=trough, leafKg=kg, **defaults)


class LeafIntakeRuleTests(TestCase):
    """模型层规则：任何入口都无法跳过装叶量校验而签收成功。"""

    def setUp(self):
        self.garden = Garden.objects.create(name="测试园", altitudeBand="800m")
        self.trough = Trough.objects.create(
            garden=self.garden,
            troughCode="T-01",
            cultivar="福鼎大白",
            loadKg=Decimal("100.00"),
            status=Trough.STATUS_LOADING,
        )

    def test_leaf_kg_must_be_positive(self):
        for bad in (Decimal("0"), Decimal("-5")):
            with self.assertRaises(ValidationError):
                _make_intake(self.trough, bad).save()
        self.assertEqual(LeafIntake.objects.count(), 0)

    def test_only_loading_trough_can_receive(self):
        # 萎凋中拒绝
        self.trough.status = Trough.STATUS_WITHERING
        self.trough.save()
        with self.assertRaises(ValidationError):
            _make_intake(self.trough, Decimal("10")).save()
        # 可下槽拒绝（先满足最新批次实测含水率 ≤ 40 的下槽规则）
        WitherBatch.objects.create(
            trough=self.trough,
            startedAt=timezone.now(),
            targetMoisture=Decimal("38.00"),
            actualMoisture=Decimal("35.00"),
            rollGrade="一级",
        )
        self.trough.status = Trough.STATUS_READY
        self.trough.save()
        with self.assertRaises(ValidationError):
            _make_intake(self.trough, Decimal("10")).save()
        self.assertEqual(LeafIntake.objects.count(), 0)

    def test_cumulative_limit_rejects_and_echoes_accumulated(self):
        _make_intake(self.trough, Decimal("80.00")).save()
        with self.assertRaises(ValidationError) as ctx:
            LeafIntake.objects.create(
                trough=self.trough,
                leafKg=Decimal("30.00"),
                receivedAt=timezone.now(),
                supplierVillage="云雾村",
                receiver="witherer",
            )
        # 回显已累计千克
        self.assertIn("80.00", str(ctx.exception))
        self.assertEqual(LeafIntake.objects.count(), 1)

    def test_single_intake_capped_by_latest_batch_target_moisture(self):
        WitherBatch.objects.create(
            trough=self.trough,
            startedAt=timezone.now(),
            targetMoisture=Decimal("40.00"),
            rollGrade="待评",
        )
        # 等于上限允许
        _make_intake(self.trough, Decimal("40.00")).save()
        with self.assertRaises(ValidationError):
            _make_intake(self.trough, Decimal("40.01")).save()

    def test_reversed_intake_not_counted_in_accumulation(self):
        intake = _make_intake(self.trough, Decimal("90.00"))
        intake.save()
        intake.isReversed = True
        intake.reversedAt = timezone.now()
        intake.reversedBy = "admin"
        intake.save()
        # 冲销后不再占用装叶量
        _make_intake(self.trough, Decimal("90.00")).save()
        self.assertEqual(
            LeafIntake.accumulated_kg(self.trough), Decimal("90.00")
        )


class LeafIntakeViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            "admin", "admin@example.com", "pw123456"
        )
        self.worker = User.objects.create_user(
            "witherer", "witherer@example.com", "pw123456"
        )
        self.garden = Garden.objects.create(name="测试园", altitudeBand="800m")
        self.trough = Trough.objects.create(
            garden=self.garden,
            troughCode="T-01",
            cultivar="福鼎大白",
            loadKg=Decimal("100.00"),
            status=Trough.STATUS_LOADING,
        )

    def _post_data(self, kg="10"):
        return {
            "trough": self.trough.pk,
            "leafKg": kg,
            "receivedAt": "2026-09-25T08:00",
            "supplierVillage": "云雾村",
            "receiver": "witherer",
        }

    def test_worker_can_create_intake(self):
        self.client.login(username="witherer", password="pw123456")
        response = self.client.post(reverse("intake_create"), self._post_data("10"))
        self.assertRedirects(response, reverse("intake_list"))
        self.assertEqual(LeafIntake.objects.count(), 1)

    def test_over_limit_post_is_rejected_with_accumulated_echo(self):
        _make_intake(self.trough, Decimal("80.00")).save()
        self.client.login(username="witherer", password="pw123456")
        response = self.client.post(reverse("intake_create"), self._post_data("30"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "80.00")  # 回显已累计千克
        self.assertEqual(LeafIntake.objects.count(), 1)

    def test_withering_trough_post_is_rejected(self):
        self.trough.status = Trough.STATUS_WITHERING
        self.trough.save()
        self.client.login(username="witherer", password="pw123456")
        response = self.client.post(reverse("intake_create"), self._post_data("10"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(LeafIntake.objects.count(), 0)

    def test_worker_cannot_reverse(self):
        intake = _make_intake(self.trough, Decimal("10"))
        intake.save()
        self.client.login(username="witherer", password="pw123456")
        self.client.post(reverse("intake_reverse", args=[intake.pk]))
        intake.refresh_from_db()
        self.assertFalse(intake.isReversed)

    def test_admin_can_reverse_and_list_excludes_reversed(self):
        intake = _make_intake(self.trough, Decimal("10"))
        intake.save()
        self.client.login(username="admin", password="pw123456")
        self.client.post(reverse("intake_reverse", args=[intake.pk]))
        intake.refresh_from_db()
        self.assertTrue(intake.isReversed)
        self.assertEqual(intake.reversedBy, "admin")
        response = self.client.get(reverse("intake_list"))
        self.assertNotContains(response, "云雾村")

    def test_home_weekly_total_matches_this_week_rows(self):
        now = timezone.now()
        _make_intake(self.trough, Decimal("40.00"), receivedAt=now).save()
        _make_intake(
            self.trough,
            Decimal("40.00"),
            receivedAt=now,
            supplierVillage="竹影村",
        ).save()
        _make_intake(
            self.trough,
            Decimal("15.00"),
            receivedAt=now - timedelta(days=7),
            supplierVillage="上周村",
        ).save()
        self.client.login(username="witherer", password="pw123456")
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["week_intake_kg"], Decimal("80.00"))
