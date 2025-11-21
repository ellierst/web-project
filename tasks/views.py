from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Task
from .serializers import TaskSerializer, TaskCreateSerializer, UserRegistrationSerializer
from .tasks import calculate_fibonacci_task
from rest_framework.decorators import api_view, permission_classes

from django.conf import settings

class UserRegistrationView(viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {'id': user.id, 'username': user.username},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Task.objects.filter(user=self.request.user)
    
    def create(self, request):
        serializer = TaskCreateSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        server_port = request.META.get('SERVER_PORT', 'unknown')
        server_url = f"http://127.0.0.1:{server_port}"
        
        task = Task.objects.create(
            user=request.user,
            number=serializer.validated_data['number'],
            status='in_progress',
            server_url=server_url
        )
 
        calculate_fibonacci_task(task.id, task.number)
        
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        tasks = Task.objects.filter(
            user=request.user,
            status__in=['in_progress']
        ).order_by('-created_at')
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def history(self, request):
        tasks = Task.objects.filter(
            user=request.user,
            status__in=['completed', 'failed', 'cancelled']
        ).order_by('-completed_at')
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        task = self.get_object()
        
        if task.status not in ['in_progress']:
            return Response(
                {'error': 'Task cannot be cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        task.status = 'cancelled'
        task.save()
        
        return Response(TaskSerializer(task).data)
    
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        task = self.get_object()
        return Response({
            'id': task.id,
            'status': task.status,
            'progress': task.progress,
            'result': task.result
        })
    
@api_view(['GET'])
@permission_classes([AllowAny])
def server_status(request):
    server_port = request.META.get('SERVER_PORT', 'unknown')
    server_url = f"http://127.0.0.1:{server_port}"

    in_progress_count = Task.objects.filter(
        status='in_progress',
        server_url=server_url
    ).count()

    available_slots = settings.MAX_TASKS_PER_SERVER - in_progress_count
    busy = in_progress_count >= settings.MAX_TASKS_PER_SERVER

    return Response({
        'busy': busy,
        'in_progress_tasks': in_progress_count,
        'available_slots': max(0, available_slots),
        'server_url': server_url,
        'max_tasks': settings.MAX_TASKS_PER_SERVER
    })