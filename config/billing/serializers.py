from decimal import Decimal
from rest_framework import serializers
from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for Product model supporting full CRUD, input sanitization,
    distributor scoping, and dual stock/stock_quantity representation.
    """
    stock_quantity = serializers.IntegerField(
        required=False,
        min_value=0,
        help_text="Alias for stock quantity"
    )
    distributor_username = serializers.CharField(
        source="distributor.username",
        read_only=True
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "category",
            "description",
            "price",
            "stock",
            "stock_quantity",
            "unit",
            "gst_rate",
            "is_active",
            "distributor_id",
            "distributor_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "distributor_id",
            "distributor_username",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "name": {
                "error_messages": {
                    "blank": "Product name is required.",
                    "required": "Product name is required."
                }
            },
            "price": {
                "error_messages": {
                    "required": "Price is required.",
                    "invalid": "Enter a valid decimal price."
                }
            }
        }

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        # If stock_quantity is passed but stock is omitted, copy stock_quantity to stock
        if "stock_quantity" in data and "stock" not in data:
            data["stock"] = data["stock_quantity"]
        elif "stock" in data and "stock_quantity" not in data:
            data["stock_quantity"] = data["stock"]
        return super().to_internal_value(data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Ensure stock_quantity always mirrors stock in responses
        ret["stock_quantity"] = instance.stock
        return ret

    def validate_name(self, value):
        if not value:
            raise serializers.ValidationError("Product name is required.")
        val = value.strip()
        if len(val) < 2:
            raise serializers.ValidationError("Product name must be at least 2 characters.")
        if val.isdigit():
            raise serializers.ValidationError("Product name cannot consist solely of digits.")
        return val

    def validate_price(self, value):
        if value is None:
            raise serializers.ValidationError("Price is required.")
        if value < Decimal("0.00"):
            raise serializers.ValidationError("Price cannot be negative.")
        return value

    def validate_stock(self, value):
        if value is None:
            return 0
        if value < 0:
            raise serializers.ValidationError("Stock quantity cannot be negative.")
        return value

    def validate_gst_rate(self, value):
        if value is None:
            return Decimal("0.00")
        if value < Decimal("0.00") or value > Decimal("100.00"):
            raise serializers.ValidationError("GST rate must be between 0 and 100 percent.")
        return value

    def validate_sku(self, value):
        if not value:
            return None
        sku_val = value.strip()
        if not sku_val:
            return None

        # Distributor isolation for SKU uniqueness
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            existing = Product.objects.filter(
                distributor=user,
                sku__iexact=sku_val
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    f"A product with SKU '{sku_val}' already exists in your inventory."
                )

        return sku_val

    def create(self, validated_data):
        # Remove write-only alias if present
        validated_data.pop("stock_quantity", None)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["distributor"] = request.user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("stock_quantity", None)
        # Prevent tampering with distributor
        validated_data.pop("distributor", None)
        return super().update(instance, validated_data)
