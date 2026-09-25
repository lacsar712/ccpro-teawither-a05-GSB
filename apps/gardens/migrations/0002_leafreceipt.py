# Generated for LeafReceipt（鲜叶签收）

from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gardens', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LeafReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kg', models.DecimalField(decimal_places=2, max_digits=10, validators=[MinValueValidator(Decimal('0.01'))], verbose_name='鲜叶千克')),
                ('receivedAt', models.DateTimeField(default=django.utils.timezone.now, verbose_name='签收时刻')),
                ('village', models.CharField(max_length=120, verbose_name='供货村名')),
                ('receiver', models.CharField(max_length=80, verbose_name='签收人')),
                ('trough', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='receipts', to='gardens.trough', verbose_name='所属槽位')),
            ],
            options={
                'verbose_name': '鲜叶签收',
                'verbose_name_plural': '鲜叶签收',
                'ordering': ['-receivedAt', '-id'],
            },
        ),
    ]
