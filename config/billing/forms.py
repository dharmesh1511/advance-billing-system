import re
from decimal import Decimal
from django import forms
from .models import Customer, Product, Invoice, InvoiceItem



class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "name",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "pincode",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Enter customer full name",
                "id": "id_name",
                "class": "form-input"
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "Enter email address (optional)",
                "id": "id_email",
                "class": "form-input"
            }),
            "phone": forms.TextInput(attrs={
                "placeholder": "Enter 10-digit phone number",
                "id": "id_phone",
                "class": "form-input"
            }),
            "address": forms.Textarea(attrs={
                "placeholder": "Enter complete customer address (optional)",
                "id": "id_address",
                "class": "form-textarea",
                "rows": 3
            }),
            "city": forms.TextInput(attrs={
                "placeholder": "Enter city (optional)",
                "id": "id_city",
                "class": "form-input"
            }),
            "state": forms.TextInput(attrs={
                "placeholder": "Enter state (optional)",
                "id": "id_state",
                "class": "form-input"
            }),
            "pincode": forms.TextInput(attrs={
                "placeholder": "Enter 6-digit pincode (optional)",
                "id": "id_pincode",
                "class": "form-input"
            }),
        }
        error_messages = {
            "name": {
                "required": "Please enter a valid customer name.",
                "invalid": "Please enter a valid customer name."
            },
            "email": {
                "invalid": "Please enter a valid email address."
            },
            "phone": {
                "required": "Please enter a valid 10-digit phone number.",
                "invalid": "Please enter a valid 10-digit phone number."
            }
        }

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name or len(name) < 2 or len(name) > 150:
            raise forms.ValidationError("Please enter a valid customer name.")
        if name.isdigit():
            raise forms.ValidationError("Please enter a valid customer name.")
        return name

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            email = email.strip()
            if not email:
                return None
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        if not re.match(r"^[6-9]\d{9}$", phone):
            raise forms.ValidationError("Please enter a valid 10-digit phone number.")
        return phone

    def clean_address(self):
        address = self.cleaned_data.get("address")
        if address:
            address = address.strip()
            if not address:
                return None
        return address

    def clean_city(self):
        city = self.cleaned_data.get("city")
        if city:
            city = city.strip()
            if not city:
                return None
            if len(city) > 100 or re.search(r"\d", city):
                raise forms.ValidationError("Please enter a valid city.")
        return city

    def clean_state(self):
        state = self.cleaned_data.get("state")
        if state:
            state = state.strip()
            if not state:
                return None
            if len(state) > 100 or re.search(r"\d", state):
                raise forms.ValidationError("Please enter a valid state.")
        return state

    def clean_pincode(self):
        pincode = self.cleaned_data.get("pincode")
        if pincode:
            pincode = pincode.strip()
            if not pincode:
                return None
            if not re.match(r"^\d{6}$", pincode):
                raise forms.ValidationError("Please enter a valid 6-digit pincode.")
        return pincode


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "category",
            "sku",
            "price",
            "stock",
            "gst_rate",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Enter product name",
                "id": "id_name",
                "class": "form-input",
                "required": True
            }),
            "category": forms.TextInput(attrs={
                "placeholder": "Enter product category (e.g. Electronics)",
                "id": "id_category",
                "class": "form-input"
            }),
            "sku": forms.TextInput(attrs={
                "placeholder": "Enter product SKU / code",
                "id": "id_sku",
                "class": "form-input"
            }),
            "price": forms.NumberInput(attrs={
                "placeholder": "Enter selling price (e.g. 499.00)",
                "id": "id_price",
                "class": "form-input",
                "step": "0.01",
                "min": "0.01",
                "required": True
            }),
            "stock": forms.NumberInput(attrs={
                "placeholder": "Enter available stock quantity",
                "id": "id_stock",
                "class": "form-input",
                "min": "0",
                "step": "1",
                "required": True
            }),
            "gst_rate": forms.NumberInput(attrs={
                "placeholder": "Enter GST rate % (0 to 100)",
                "id": "id_gst_rate",
                "class": "form-input",
                "step": "0.01",
                "min": "0",
                "max": "100"
            }),
            "description": forms.Textarea(attrs={
                "placeholder": "Enter detailed product description (optional)",
                "id": "id_description",
                "class": "form-textarea",
                "rows": 3
            }),
        }
        error_messages = {
            "name": {
                "required": "Please enter a valid product name.",
                "invalid": "Please enter a valid product name."
            },
            "price": {
                "required": "Price must be greater than 0.",
                "invalid": "Price must be a valid number greater than 0."
            },
            "stock": {
                "required": "Stock cannot be negative.",
                "invalid": "Stock must be a valid whole number."
            },
            "gst_rate": {
                "invalid": "GST rate must be between 0% and 100%."
            }
        }

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("Please enter a valid product name.")
        if len(name) > 200:
            raise forms.ValidationError("Product name cannot exceed 200 characters.")
        return name

    def clean_category(self):
        category = self.cleaned_data.get("category")
        if category:
            category = category.strip()
            if not category:
                return None
            if len(category) > 100:
                raise forms.ValidationError("Category cannot exceed 100 characters.")
        return category

    def clean_sku(self):
        sku = self.cleaned_data.get("sku")
        if sku:
            sku = sku.strip()
            if not sku:
                return None
            if len(sku) > 100:
                raise forms.ValidationError("SKU cannot exceed 100 characters.")
        return sku

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is None or price <= Decimal("0.00"):
            raise forms.ValidationError("Price must be greater than 0.")
        return price

    def clean_stock(self):
        stock = self.cleaned_data.get("stock")
        if stock is None or stock < 0:
            raise forms.ValidationError("Stock cannot be negative.")
        return stock

    def clean_gst_rate(self):
        gst_rate = self.cleaned_data.get("gst_rate")
        if gst_rate is None:
            return Decimal("0.00")
        if gst_rate < Decimal("0.00") or gst_rate > Decimal("100.00"):
            raise forms.ValidationError("GST rate must be between 0% and 100%.")
        return gst_rate

    def clean_description(self):
        description = self.cleaned_data.get("description")
        if description:
            description = description.strip()
            if not description:
                return None
        return description



class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "name",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "pincode",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Enter customer full name",
                "id": "id_name",
                "class": "form-input"
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "Enter email address (optional)",
                "id": "id_email",
                "class": "form-input"
            }),
            "phone": forms.TextInput(attrs={
                "placeholder": "Enter 10-digit phone number",
                "id": "id_phone",
                "class": "form-input"
            }),
            "address": forms.Textarea(attrs={
                "placeholder": "Enter complete customer address (optional)",
                "id": "id_address",
                "class": "form-textarea",
                "rows": 3
            }),
            "city": forms.TextInput(attrs={
                "placeholder": "Enter city (optional)",
                "id": "id_city",
                "class": "form-input"
            }),
            "state": forms.TextInput(attrs={
                "placeholder": "Enter state (optional)",
                "id": "id_state",
                "class": "form-input"
            }),
            "pincode": forms.TextInput(attrs={
                "placeholder": "Enter 6-digit pincode (optional)",
                "id": "id_pincode",
                "class": "form-input"
            }),
        }
        error_messages = {
            "name": {
                "required": "Please enter a valid customer name.",
                "invalid": "Please enter a valid customer name."
            },
            "email": {
                "invalid": "Please enter a valid email address."
            },
            "phone": {
                "required": "Please enter a valid 10-digit phone number.",
                "invalid": "Please enter a valid 10-digit phone number."
            }
        }

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name or len(name) < 2 or len(name) > 150:
            raise forms.ValidationError("Please enter a valid customer name.")
        if name.isdigit():
            raise forms.ValidationError("Please enter a valid customer name.")
        return name

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            email = email.strip()
            if not email:
                return None
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        if not re.match(r"^[6-9]\d{9}$", phone):
            raise forms.ValidationError("Please enter a valid 10-digit phone number.")
        return phone

    def clean_address(self):
        address = self.cleaned_data.get("address")
        if address:
            address = address.strip()
            if not address:
                return None
        return address

    def clean_city(self):
        city = self.cleaned_data.get("city")
        if city:
            city = city.strip()
            if not city:
                return None
            if len(city) > 100 or re.search(r"\d", city):
                raise forms.ValidationError("Please enter a valid city.")
        return city

    def clean_state(self):
        state = self.cleaned_data.get("state")
        if state:
            state = state.strip()
            if not state:
                return None
            if len(state) > 100 or re.search(r"\d", state):
                raise forms.ValidationError("Please enter a valid state.")
        return state

    def clean_pincode(self):
        pincode = self.cleaned_data.get("pincode")
        if pincode:
            pincode = pincode.strip()
            if not pincode:
                return None
            if not re.match(r"^\d{6}$", pincode):
                raise forms.ValidationError("Please enter a valid 6-digit pincode.")
        return pincode


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["customer", "invoice_date"]
        widgets = {
            "customer": forms.Select(attrs={
                "class": "form-input",
                "id": "id_customer",
                "required": True
            }),
            "invoice_date": forms.DateInput(attrs={
                "type": "date",
                "class": "form-input",
                "id": "id_invoice_date",
                "required": True
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["customer"].queryset = Customer.objects.filter(distributor=user)
        else:
            self.fields["customer"].queryset = Customer.objects.none()
        self.fields["customer"].empty_label = "Select Customer"
        if not self.initial.get("invoice_date"):
            import datetime
            self.initial["invoice_date"] = datetime.date.today().strftime("%Y-%m-%d")

    def clean_customer(self):
        customer = self.cleaned_data.get("customer")
        if not customer:
            raise forms.ValidationError("Please select a valid customer.")
        return customer

    def clean_invoice_date(self):
        invoice_date = self.cleaned_data.get("invoice_date")
        if not invoice_date:
            raise forms.ValidationError("Please select a valid invoice date.")
        return invoice_date

    def clean(self):
        cleaned_data = super().clean()
        if not getattr(self.instance, "invoice_number", None):
            self.instance.invoice_number = "PENDING"
        return cleaned_data


class InvoiceItemForm(forms.ModelForm):
    discount_percent = forms.DecimalField(
        required=False,
        initial=Decimal("0.00"),
        min_value=Decimal("0.00"),
        max_value=Decimal("100.00"),
        widget=forms.NumberInput(attrs={
            "class": "form-input discount-input",
            "min": "0",
            "max": "100",
            "step": "0.01",
            "value": "0",
            "placeholder": "0"
        }),
        error_messages={
            "invalid": "Discount must be between 0% and 100%.",
            "min_value": "Discount must be between 0% and 100%.",
            "max_value": "Discount must be between 0% and 100%."
        }
    )

    class Meta:
        model = InvoiceItem
        fields = ["product", "quantity", "discount_percent"]
        widgets = {
            "product": forms.Select(attrs={
                "class": "form-input product-select",
                "required": True
            }),
            "quantity": forms.NumberInput(attrs={
                "class": "form-input quantity-input",
                "min": "1",
                "step": "1",
                "value": "1",
                "required": True
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["product"].queryset = Product.objects.filter(distributor=user)
        else:
            self.fields["product"].queryset = Product.objects.none()
        self.fields["product"].empty_label = "Select Product"
        if not self.initial.get("discount_percent"):
            self.initial["discount_percent"] = Decimal("0.00")

    def clean_product(self):
        product = self.cleaned_data.get("product")
        if not product:
            raise forms.ValidationError("Please select a product.")
        return product

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")
        if quantity is None or quantity < 1:
            raise forms.ValidationError("Quantity must be at least 1.")
        return quantity

    def clean_discount_percent(self):
        discount = self.cleaned_data.get("discount_percent")
        if discount is None:
            return Decimal("0.00")
        if discount < Decimal("0.00") or discount > Decimal("100.00"):
            raise forms.ValidationError("Discount must be between 0% and 100%.")
        return discount

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        if product:
            self.instance.product_name = product.name
            self.instance.unit_price = product.price
            self.instance.gst_rate = product.gst_rate
            self.instance.taxable_amount = Decimal("0.00")
            self.instance.gst_amount = Decimal("0.00")
            self.instance.line_total = Decimal("0.00")
        else:
            self.instance.product_name = "PENDING"
            self.instance.unit_price = Decimal("0.00")
            self.instance.gst_rate = Decimal("0.00")
            self.instance.taxable_amount = Decimal("0.00")
            self.instance.gst_amount = Decimal("0.00")
            self.instance.line_total = Decimal("0.00")
        return cleaned_data


BaseInvoiceItemFormSet = forms.inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class InvoiceItemFormSet(BaseInvoiceItemFormSet):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['user'] = self.user
        return super()._construct_form(i, **kwargs)

