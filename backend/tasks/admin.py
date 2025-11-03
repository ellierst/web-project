from django.contrib import admin
from .models import Task

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'number', 'status', 'progress', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'id']
    readonly_fields = ['created_at', 'started_at', 'completed_at']