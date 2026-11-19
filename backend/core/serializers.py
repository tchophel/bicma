from rest_framework import serializers

from .models import FAQ, AuditLog, Category, Dzongkhag, Subcategory


class SubcategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Subcategory
        fields = ["id", "category", "name", "is_active"]


class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()
    form = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "is_active", "default_division", "urban_division", "rural_division", "default_priority", "subcategories", "form"]

    def get_form(self, obj):
        from .formspecs import spec_for
        return spec_for(obj)

    def get_subcategories(self, obj):
        return [{"id": s.id, "name": s.name} for s in obj.subcategories.all() if s.is_active]


class DzongkhagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dzongkhag
        fields = ["id", "name", "is_active"]

    def validate_name(self, value):
        value = value.strip()
        qs = Dzongkhag.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This Dzongkhag already exists.")
        return value


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ["id", "actor_email", "action", "entity_type", "entity_id", "detail", "ip_address", "created_at"]


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ["id", "question", "answer", "position", "is_active"]
