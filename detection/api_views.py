# detection/api_views.py
from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Camera, DetectionRecord, DailyReport
from .serializers import CameraSerializer, DetectionRecordSerializer

@api_view(['GET'])
def camera_list(request):
    """Lista de cámaras para el frontend"""
    cameras = Camera.objects.filter(is_active=True)
    serializer = CameraSerializer(cameras, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def detection_history(request, camera_id):
    """Historial de detecciones para gráficos"""
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    
    records = DetectionRecord.objects.filter(camera_id=camera_id)
    
    if from_date:
        records = records.filter(timestamp__date__gte=from_date)
    if to_date:
        records = records.filter(timestamp__date__lte=to_date)
        
    serializer = DetectionRecordSerializer(records.order_by('timestamp'), many=True)
    return Response(serializer.data)

@api_view(['GET'])
def occupancy_stats(request):
    """Estadísticas para el dashboard"""
    import json
    from django.db.models import Avg, Max
    
    stats = DetectionRecord.objects.values('camera__name').annotate(
        avg_occupancy=Avg('occupancy_rate'),
        peak_occupancy=Max('person_count')
    )
    
    return Response(list(stats))