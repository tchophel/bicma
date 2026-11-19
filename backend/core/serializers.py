from rest_framework import serializers

from .models import FAQ, AuditLog, Category, Dzongkhag, Gewog, Subcategory


class SubcategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Subcategory
        fields = ["id", "category", "name", "is_active"]


class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "is_active", "default_division", "urban_division", "rural_division", "default_priority", "subcategories"]

    def get_subcategories(self, obj):
        return [{"id": s.id, "name": s.name} for s in obj.subcategories.all() if s.is_active]


class DzongkhagSerializer(serializers.ModelSerializer):
    gewog_count = serializers.IntegerField(source="gewogs.count", read_only=True)

    class Meta:
        model = Dzongkhag
        fields = ["id", "name", "is_active", "gewog_count"]

    def validate_name(self, value):
        value = value.strip()
        qs = Dzongkhag.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This Dzongkhag already exists.")
        return value


class GewogSerializer(serializers.ModelSerializer):
    dzongkhag_name = serializers.CharField(source="dzongkhag.name", read_only=True)

    class Meta:
        model = Gewog
        fields = ["id", "dzongkhag", "dzongkhag_name", "name", "is_active"]

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", "")).strip()
        dz = attrs.get("dzongkhag", getattr(self.instance, "dzongkhag", None))
        qs = Gewog.objects.filter(dzongkhag=dz, name__iexact=name)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({"name": "This Gewog already exists in the selected Dzongkhag."})
        attrs["name"] = name
        return attrs


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ["id", "actor_email", "action", "entity_type", "entity_id", "detail", "ip_address", "created_at"]


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ["id", "question", "answer", "position", "is_active"]
