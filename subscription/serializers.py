from rest_framework import serializers
from .models import SubscriptionPlan, Subscription, FeatureUsage, SubscriptionUsageLog

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Serializer for subscription plans
    """
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'description', 'price', 'duration_days',
            'features', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

class FeatureUsageSerializer(serializers.ModelSerializer):
    """
    Serializer for feature usage tracking
    """
    class Meta:
        model = FeatureUsage
        fields = ['feature_name', 'usage_count', 'last_used']
        read_only_fields = ['last_used']

class SubscriptionUsageLogSerializer(serializers.ModelSerializer):
    """
    Serializer for subscription usage logs
    """
    class Meta:
        model = SubscriptionUsageLog
        fields = ['action', 'timestamp', 'details']
        read_only_fields = ['timestamp']

class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for user subscriptions
    """
    plan = SubscriptionPlanSerializer(read_only=True)
    feature_usage = FeatureUsageSerializer(many=True, read_only=True)
    recent_activity = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            'id', 'user', 'plan', 'status', 'start_date', 'end_date',
            'feature_usage', 'recent_activity', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_recent_activity(self, obj):
        """Get recent activity logs for the subscription"""
        logs = SubscriptionUsageLog.objects.filter(
            subscription=obj
        ).order_by('-timestamp')[:5]
        return SubscriptionUsageLogSerializer(logs, many=True).data

class SubscriptionCreateSerializer(serializers.Serializer):
    """
    Serializer for creating new subscriptions
    """
    plan_id = serializers.IntegerField()
    payment_method_id = serializers.CharField(required=False, allow_null=True)

    def validate_plan_id(self, value):
        try:
            plan = SubscriptionPlan.objects.get(id=value, is_active=True)
            return value
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive subscription plan")

class SubscriptionSummarySerializer(serializers.Serializer):
    """
    Serializer for subscription summary
    """
    has_active_subscription = serializers.BooleanField()
    subscription = serializers.DictField(allow_null=True)
    feature_usage = serializers.DictField(allow_null=True)
    recent_activity = serializers.ListField(allow_null=True) 