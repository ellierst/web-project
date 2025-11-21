from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Task
from django.conf import settings

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    
    class Meta:
        model = User
        fields = ['username', 'password']
    
    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password']
        )
        return user

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            'id', 'number', 'status', 'progress', 'result', 
            'error_message', 'server_url', 'created_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'status', 'progress', 'result', 'error_message',
            'server_url', 'created_at', 'completed_at'
        ]
    
    def validate_number(self, value):
        if value < 0:
            raise serializers.ValidationError("Number must be non-negative")
        if value > settings.MAX_FIBONACCI_NUMBER:
            raise serializers.ValidationError(
                f"Number too large. Maximum: {settings.MAX_FIBONACCI_NUMBER}"
            )
        return value

class TaskCreateSerializer(serializers.Serializer):
    number = serializers.IntegerField(min_value=0, max_value=settings.MAX_FIBONACCI_NUMBER)
    
    def validate_number(self, value):
        user = self.context['request'].user
        active_tasks = Task.objects.filter(
            user=user,
            status__in=['in_progress']
        ).count()
        
        if active_tasks >= settings.MAX_TASKS_PER_USER:
            raise serializers.ValidationError(
                f"Maximum active tasks ({settings.MAX_TASKS_PER_USER}) reached"
            )

        return value