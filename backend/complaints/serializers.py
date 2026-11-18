from django.utils import timezone
from rest_framework import serializers

from accounts.models import Division
from core.models import Category, Dzongkhag, Gewog, Subcategory

from .models import Complaint, StatusHistory

CREATE_FIELDS = [
    "complainant_name", "phone", "email", "dzongkhag", "gewog", "preferred_contact",
    "on_behalf", "affected_name", "affected_relationship", "affected_contact",
    "category", "division", "subcategory", "subject", "description", "incident_date", "platform",
    "website_or_social", "additional_info",
]


class ComplaintCreateSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.filter(is_active=True), required=False, allow_null=True)
    division = serializers.PrimaryKeyRelatedField(queryset=Division.objects.filter(is_active=True), required=False)
    subcategory = serializers.PrimaryKeyRelatedField(
        queryset=Subcategory.objects.filter(is_active=True), required=False, allow_null=True
    )

    dzongkhag = serializers.PrimaryKeyRelatedField(queryset=Dzongkhag.objects.filter(is_active=True), required=False, allow_null=True)
    gewog = serializers.PrimaryKeyRelatedField(queryset=Gewog.objects.filter(is_active=True), required=False, allow_null=True)

    class Meta:
        model = Complaint
        fields = CREATE_FIELDS
        extra_kwargs = {"description": {"max_length": 10000}}

    def validate_incident_date(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError("The incident date cannot be in the future.")
        return value

    def validate(self, attrs):
        offline = self.context.get("offline", False)
        if not offline:
            if not attrs.get("phone") and not attrs.get("email"):
                raise serializers.ValidationError({"phone": "Provide a contact number or an email address."})
            if not attrs.get("dzongkhag"):
                raise serializers.ValidationError({"dzongkhag": "Select a Dzongkhag."})
        dz, gw = attrs.get("dzongkhag"), attrs.get("gewog")
        if gw and not dz:
            raise serializers.ValidationError({"dzongkhag": "Select the Dzongkhag for the chosen Gewog."})
        if gw and gw.dzongkhag_id != dz.pk:
            raise serializers.ValidationError({"gewog": "This Gewog does not belong to the selected Dzongkhag."})
        if not attrs.get("category") and not attrs.get("division"):
            raise serializers.ValidationError({"division": "Select a division."})
        sub = attrs.get("subcategory")
        if sub and (not attrs.get("category") or sub.category_id != attrs["category"].pk):
            raise serializers.ValidationError({"subcategory": "Subcategory does not belong to the selected category."})
        if attrs.get("on_behalf"):
            for f in ("affected_name", "affected_relationship"):
                if not attrs.get(f):
                    raise serializers.ValidationError({f: "Required when submitting on behalf of another person."})
        else:
            for f in ("affected_name", "affected_relationship", "affected_contact"):
                attrs[f] = ""
        return attrs


class StatusHistorySerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.username", default=None, read_only=True)

    class Meta:
        model = StatusHistory
        fields = ["previous_status", "new_status", "actor", "reason", "created_at"]


class ComplaintListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="Uncategorized")
    division_name = serializers.CharField(source="division.name", read_only=True, default=None)
    assigned_to_name = serializers.SerializerMethodField()
    dzongkhag_name = serializers.CharField(source="dzongkhag.name", read_only=True, default=None)
    internal_status_display = serializers.CharField(source="get_internal_status_display", read_only=True)
    public_status = serializers.CharField(read_only=True)

    class Meta:
        model = Complaint
        fields = [
            "id", "reference", "subject", "channel", "category", "category_name", "division", "division_name",
            "assigned_to", "assigned_to_name", "internal_status", "internal_status_display", "public_status",
            "complainant_name", "dzongkhag", "dzongkhag_name", "created_at",
        ]

    def get_assigned_to_name(self, obj):
        return obj.assigned_to.get_full_name() or obj.assigned_to.username if obj.assigned_to else None


class ComplaintDetailSerializer(ComplaintListSerializer):
    subcategory_name = serializers.CharField(source="subcategory.name", read_only=True, default=None)
    gewog_name = serializers.CharField(source="gewog.name", read_only=True, default=None)
    registered_by_name = serializers.CharField(source="registered_by.username", read_only=True, default=None)
    status_history = StatusHistorySerializer(many=True, read_only=True)

    class Meta(ComplaintListSerializer.Meta):
        fields = ComplaintListSerializer.Meta.fields + CREATE_FIELDS[1:3] + [
            "gewog", "gewog_name", "preferred_contact", "on_behalf", "affected_name", "affected_relationship",
            "affected_contact", "subcategory", "subcategory_name", "description", "incident_date", "platform",
            "website_or_social", "additional_info", "registered_by_name", "updated_at", "status_history",
        ]


class PublicTrackSerializer(serializers.ModelSerializer):
    """Reference-only tracking: status and dates ONLY. The reference alone is not strong
    authentication, so no subject, category, description, contact or officer data is returned."""

    public_status = serializers.CharField(read_only=True)
    public_status_display = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = ["reference", "public_status", "public_status_display", "created_at", "updated_at"]

    def get_public_status_display(self, obj):
        from .models import PublicStatus
        return PublicStatus(obj.public_status).label
