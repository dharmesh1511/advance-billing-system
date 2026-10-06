# Generated for Invoice and InvoiceItem models

import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_product'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('invoice_number', models.CharField(help_text='Invoice reference number', max_length=50)),
                ('invoice_date', models.DateField(help_text='Date of invoice issuance')),
                ('subtotal', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Subtotal before taxes', max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('total_gst', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Total GST amount', max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('grand_total', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Grand total amount including GST', max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(help_text='The customer for this invoice', on_delete=django.db.models.deletion.PROTECT, related_name='invoices', to='billing.customer')),
                ('distributor', models.ForeignKey(help_text='The distributor account this invoice belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='invoices', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Invoice',
                'verbose_name_plural': 'Invoices',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='InvoiceItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product_name', models.CharField(help_text='Snapshot of product name at invoice creation time', max_length=200)),
                ('quantity', models.PositiveIntegerField(default=1, help_text='Quantity purchased', validators=[django.core.validators.MinValueValidator(1)])),
                ('unit_price', models.DecimalField(decimal_places=2, help_text='Snapshot of unit price at invoice creation time', max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('gst_rate', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Snapshot of GST rate percentage at invoice creation time', max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal('0.00')), django.core.validators.MaxValueValidator(Decimal('100.00'))])),
                ('taxable_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Taxable amount (quantity * unit_price)', max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('gst_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='GST amount for this line item', max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('line_total', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Line total amount (taxable_amount + gst_amount)', max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('invoice', models.ForeignKey(help_text='The parent invoice', on_delete=django.db.models.deletion.CASCADE, related_name='items', to='billing.invoice')),
                ('product', models.ForeignKey(help_text='The product item', on_delete=django.db.models.deletion.PROTECT, related_name='invoice_items', to='billing.product')),
            ],
            options={
                'verbose_name': 'Invoice Item',
                'verbose_name_plural': 'Invoice Items',
                'ordering': ['id'],
            },
        ),
        migrations.AddConstraint(
            model_name='invoice',
            constraint=models.UniqueConstraint(fields=('distributor', 'invoice_number'), name='unique_invoice_number_per_distributor'),
        ),
    ]
