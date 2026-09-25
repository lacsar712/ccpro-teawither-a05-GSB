from django import forms
from django.utils import timezone

from .models import Garden, LeafReceipt, Trough, WitherBatch


class GardenForm(forms.ModelForm):
    class Meta:
        model = Garden
        fields = ["name", "altitudeBand", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}),
            "altitudeBand": forms.TextInput(attrs={"class": "input"}),
            "notes": forms.Textarea(attrs={"class": "input", "rows": 3}),
        }


class TroughForm(forms.ModelForm):
    class Meta:
        model = Trough
        fields = ["garden", "troughCode", "cultivar", "loadKg", "status"]
        widgets = {
            "garden": forms.Select(attrs={"class": "input"}),
            "troughCode": forms.TextInput(attrs={"class": "input"}),
            "cultivar": forms.TextInput(attrs={"class": "input"}),
            "loadKg": forms.NumberInput(attrs={"class": "input", "step": "0.01"}),
            "status": forms.Select(attrs={"class": "input"}),
        }


class WitherBatchForm(forms.ModelForm):
    class Meta:
        model = WitherBatch
        fields = [
            "trough",
            "startedAt",
            "targetMoisture",
            "actualMoisture",
            "rollGrade",
        ]
        widgets = {
            "trough": forms.Select(attrs={"class": "input"}),
            "startedAt": forms.DateTimeInput(
                attrs={"class": "input", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "targetMoisture": forms.NumberInput(
                attrs={"class": "input", "step": "0.01"}
            ),
            "actualMoisture": forms.NumberInput(
                attrs={"class": "input", "step": "0.01"}
            ),
            "rollGrade": forms.TextInput(attrs={"class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["startedAt"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        if self.instance and self.instance.pk and self.instance.startedAt:
            local = timezone.localtime(self.instance.startedAt)
            self.initial["startedAt"] = local.strftime("%Y-%m-%dT%H:%M")


class LeafReceiptForm(forms.ModelForm):
    class Meta:
        model = LeafReceipt
        fields = ["trough", "kg", "receivedAt", "village", "receiver"]
        widgets = {
            "trough": forms.Select(attrs={"class": "input"}),
            "kg": forms.NumberInput(
                attrs={"class": "input", "step": "0.01", "min": "0.01"}
            ),
            "receivedAt": forms.DateTimeInput(
                attrs={"class": "input", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "village": forms.TextInput(attrs={"class": "input"}),
            "receiver": forms.TextInput(attrs={"class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["receivedAt"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]
        # 仅装叶中槽可签收；萎凋中与可下槽槽位不出现在选择中。
        self.fields["trough"].queryset = Trough.objects.filter(
            status=Trough.STATUS_LOADING
        ).select_related("garden")
        if not self.instance or not self.instance.pk:
            self.initial["receivedAt"] = timezone.localtime().strftime(
                "%Y-%m-%dT%H:%M"
            )
        elif self.instance.receivedAt:
            self.initial["receivedAt"] = timezone.localtime(
                self.instance.receivedAt
            ).strftime("%Y-%m-%dT%H:%M")

    def clean_kg(self):
        kg = self.cleaned_data.get("kg")
        if kg is not None and kg <= 0:
            raise forms.ValidationError("鲜叶千克必须为正数。")
        return kg
