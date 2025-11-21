import os
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from tasks.views import TaskViewSet, UserRegistrationView, server_status

router = DefaultRouter()
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'auth', UserRegistrationView, basename='auth')

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/server-status/', server_status, name='server_status'),
    path('', TemplateView.as_view(template_name='frontend.html'), name='index'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                      document_root=settings.STATICFILES_DIRS[0])
