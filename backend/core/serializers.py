from rest_framework import serializers

from .models import AuditLog, Category, Dzongkhag, FormQuestion, Subcategory


class SubcategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Subcategory
        fields = ["id", "category", "name", "is_active"]


class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()
    form = serializers.SerializerMethodField()
    extra_fields = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "is_active", "default_division", "urban_division", "rural_division", "default_priority", "description", "subcategories", "form", "extra_fields"]

    def get_form(self, obj):
        from .formspecs import spec_for
        return spec_for(obj)

    def get_extra_fields(self, obj):
        from .formspecs import custom_fields_for
        return custom_fields_for(obj)

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


class FormQuestionSerializer(serializers.ModelSerializer):
    """A question added to a division's complaint form (Administrator > Form builder)."""

    division_name = serializers.CharField(source="division.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True, default="")

    class Meta:
        model = FormQuestion
        fields = ["id", "key", "division", "division_name", "category", "category_name", "label", "kind", "options", "required", "hint", "position", "is_active"]
        read_only_fields = ["key"]

    def validate_label(self, value):
        value = " ".join(value.split())
        if len(value) < 3:
            raise serializers.ValidationError("Write the question, at least 3 characters.")
        return value

    def validate_options(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Options must be a list.")
        clean = list(dict.fromkeys(" ".join(str(x).split()) for x in value if str(x).strip()))
        if len(clean) > 40 or any(len(x) > 150 for x in clean):
            raise serializers.ValidationError("Use at most 40 options of 150 characters each.")
        return clean

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", "text"))
        options = attrs.get("options", getattr(self.instance, "options", []))
        if kind in ("select", "checks"):
            if len(options or []) < 2:
                raise serializers.ValidationError({"options": "Add at least two options, one per line."})
        else:
            attrs["options"] = []
        division = attrs.get("division", getattr(self.instance, "division", None))
        category = attrs.get("category", getattr(self.instance, "category", None))
        if category and division and category.default_division_id != division.pk:
            raise serializers.ValidationError({"category": "This category belongs to a different division."})
        return attrs
