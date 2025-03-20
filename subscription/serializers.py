from rest_framework import serializers
from .models import (
    SubscriptionPlan, UserSubscription, FeatureUsage, 
    SubscriptionUsageLog, SubscriptionFeature, PlanFeature
)

class SubscriptionFeatureSerializer(serializers.ModelSerializer):
    """
    Serializer for subscription features
    """
    class Meta:
        model = SubscriptionFeature
        fields = [
            'id', 'name', 'key', 'description', 'icon', 
            'is_highlighted', 'display_order'
        ]


class PlanFeatureSerializer(serializers.ModelSerializer):
    """
    Serializer for plan features (junction table)
    """
    feature = SubscriptionFeatureSerializer(read_only=True)
    
    class Meta:
        model = PlanFeature
        fields = [
            'id', 'feature', 'is_available', 'value_limit'
        ]


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Serializer for subscription plans
    """
    annual_price = serializers.SerializerMethodField()
    stripe_annual_price_id = serializers.SerializerMethodField()
    yearly_plan_id = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    is_yearly = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'slug', 'description', 'short_description', 'price', 
            'annual_price', 'interval', 'status', 'max_cv_generations', 
            'max_job_applications', 'max_saved_jobs', 'has_cv_analytics', 
            'has_job_alerts', 'has_priority_support', 'has_ai_interview_prep', 
            'is_popular', 'stripe_price_id', 'stripe_annual_price_id', 
            'stripe_product_id', 'yearly_plan_id', 'features', 'is_yearly',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_price(self, obj):
        """
        Format price with 2 decimal places
        """
        return round(float(obj.price), 2)
    
    def get_annual_price(self, obj):
        """
        Get the annual price - either from matching yearly plan or calculated
        """
        if obj.interval == 'year':
            return round(float(obj.price), 2)
            
        yearly_plan = SubscriptionPlan.get_yearly_plan_for(obj)
        if yearly_plan:
            return round(float(yearly_plan.price), 2)
        return obj.annual_price
    
    def get_stripe_annual_price_id(self, obj):
        """
        Get the Stripe annual price ID - either from matching yearly plan or calculated
        """
        if obj.interval == 'year':
            return obj.stripe_price_id
            
        yearly_plan = SubscriptionPlan.get_yearly_plan_for(obj)
        if yearly_plan:
            return yearly_plan.stripe_price_id
        return obj.stripe_annual_price_id
    
    def get_yearly_plan_id(self, obj):
        """
        Get the ID of the corresponding yearly plan if it exists
        """
        if obj.interval == 'year':
            return None
            
        yearly_plan = SubscriptionPlan.get_yearly_plan_for(obj)
        if yearly_plan:
            return yearly_plan.id
        return None
    
    def get_features(self, obj):
        """
        Get the features available for this plan
        """
        plan_features = PlanFeature.objects.filter(plan=obj).select_related('feature')
        return PlanFeatureSerializer(plan_features, many=True).data
    
    def get_is_yearly(self, obj):
        """
        Helper to know if this is a yearly plan
        """
        return obj.interval == 'year'


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


class UserSubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for user subscriptions
    """
    plan = SubscriptionPlanSerializer(read_only=True)
    feature_usage = FeatureUsageSerializer(many=True, read_only=True)
    recent_activity = serializers.SerializerMethodField()

    class Meta:
        model = UserSubscription
        fields = [
            'id', 'user', 'plan', 'status', 'start_date', 'end_date',
            'stripe_subscription_id', 'stripe_customer_id',
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
            plan = SubscriptionPlan.objects.get(id=value, status='active')
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