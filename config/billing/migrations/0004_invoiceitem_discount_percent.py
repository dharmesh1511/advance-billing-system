# Generated for InvoiceItem discount_percent field

import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0003_invoice_invoiceitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoiceitem',
            name='discount_percent',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Snapshot of discount percentage at invoice creation time',
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(Decimal('0.00')),
                    django.core.validators.MaxValueValidator(Decimal('100.00'))
                ]
            ),
        ),
    ]
