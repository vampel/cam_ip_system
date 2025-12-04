# detection/api_views.py - VERSIÓN ACTUALIZADA CON YOLO
from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
import json
from datetime import datetime, timedelta

# Importar modelos existentes
from .models import Camera, DetectionRecord, DailyReport
from .serializers import CameraSerializer, DetectionRecordSerializer

# Importar CameraManager para YOLO
from .camera_manager import camera_manager

@api_view(['GET'])
def camera_list(request):
    """Lista de cámaras combinando base de datos y YOLO en tiempo real"""
    try:
        # Obtener cámaras de la base de datos
        db_cameras = Camera.objects.filter(is_active=True)
        db_data = CameraSerializer(db_cameras, many=True).data
        
        # Obtener estado en tiempo real del CameraManager
        live_cameras = camera_manager.get_cameras_info()
        
        # Combinar datos
        for camera in db_data:
            camera_id = camera.get('id')
            
            # Buscar información en tiempo real
            live_info = next((c for c in live_cameras if c['id'] == str(camera_id)), None)
            
            if live_info:
                # Agregar datos en tiempo real
                camera['live_status'] = live_info.get('status', 'unknown')
                camera['person_count'] = live_info.get('person_count', 0)
                camera['last_update'] = live_info.get('last_update')
                
                # Obtener detecciones recientes
                detections = camera_manager.get_camera_detections(str(camera_id), limit=5)
                camera['recent_detections'] = detections
                camera['detection_count'] = len(detections)
                
                # Estadísticas YOLO
                stats = camera_manager.get_detection_statistics(str(camera_id))
                camera['yolo_stats'] = stats
            else:
                camera['live_status'] = 'offline'
                camera['person_count'] = 0
        
        return Response({
            'cameras': db_data,
            'live_count': len(live_cameras),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def detection_history(request, camera_id):
    """Historial de detecciones combinando DB y YOLO"""
    try:
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        source = request.GET.get('source', 'both')  # 'db', 'yolo', o 'both'
        
        response_data = {
            'camera_id': camera_id,
            'timestamp': datetime.now().isoformat()
        }
        
        # Datos de la base de datos
        if source in ['db', 'both']:
            records = DetectionRecord.objects.filter(camera_id=camera_id)
            
            if from_date:
                records = records.filter(timestamp__date__gte=from_date)
            if to_date:
                records = records.filter(timestamp__date__lte=to_date)
                
            db_serializer = DetectionRecordSerializer(records.order_by('timestamp'), many=True)
            response_data['database_records'] = db_serializer.data
            response_data['db_count'] = records.count()
        
        # Datos de YOLO en tiempo real
        if source in ['yolo', 'both']:
            # Historial de YOLO
            yolo_history = camera_manager.get_detection_history(str(camera_id), limit=100)
            
            # Filtrar por fecha si es necesario
            if from_date or to_date:
                filtered = []
                from_datetime = datetime.fromisoformat(from_date) if from_date else None
                to_datetime = datetime.fromisoformat(to_date) if to_date else None
                
                for det in yolo_history:
                    try:
                        det_time = datetime.fromisoformat(det.get('timestamp', ''))
                        
                        include = True
                        if from_datetime and det_time < from_datetime:
                            include = False
                        if to_datetime and det_time > to_datetime:
                            include = False
                        
                        if include:
                            filtered.append(det)
                    except:
                        continue
                
                yolo_history = filtered
            
            response_data['yolo_detections'] = yolo_history
            response_data['yolo_count'] = len(yolo_history)
            
            # Detecciones recientes
            recent_detections = camera_manager.get_camera_detections(str(camera_id), limit=20)
            response_data['recent_detections'] = recent_detections
        
        return Response(response_data)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def occupancy_stats(request):
    """Estadísticas combinadas de ocupación"""
    try:
        from django.db.models import Avg, Max, Count
        
        # Estadísticas de base de datos
        db_stats = DetectionRecord.objects.values('camera__name').annotate(
            avg_occupancy=Avg('occupancy_rate'),
            peak_occupancy=Max('person_count'),
            total_records=Count('id')
        )
        
        db_stats_list = list(db_stats)
        
        # Estadísticas de YOLO en tiempo real
        live_cameras = camera_manager.get_cameras_info()
        
        yolo_stats = []
        total_live_persons = 0
        active_yolo_cameras = 0
        
        for camera in live_cameras:
            camera_id = camera['id']
            person_count = camera.get('person_count', 0)
            
            stats = camera_manager.get_detection_statistics(camera_id)
            
            yolo_stats.append({
                'camera_name': camera_id,
                'live_person_count': person_count,
                'total_detections': stats.get('total_detections', 0),
                'avg_confidence': stats.get('avg_confidence', 0),
                'last_hour_count': stats.get('last_hour_count', 0),
                'status': camera.get('status', 'unknown')
            })
            
            total_live_persons += person_count
            if camera.get('status') == 'running':
                active_yolo_cameras += 1
        
        return Response({
            'database_statistics': db_stats_list,
            'yolo_live_statistics': yolo_stats,
            'summary': {
                'total_cameras_db': Camera.objects.filter(is_active=True).count(),
                'total_cameras_live': len(live_cameras),
                'active_yolo_cameras': active_yolo_cameras,
                'total_live_persons': total_live_persons,
                'avg_persons_per_camera': round(total_live_persons / max(len(live_cameras), 1), 2)
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ========== NUEVAS APIs para YOLO específicas ==========

@api_view(['GET'])
def yolo_detections(request, camera_id):
    """API específica para detecciones YOLO"""
    try:
        limit = int(request.GET.get('limit', 20))
        with_boxes = request.GET.get('boxes', 'false').lower() == 'true'
        
        # Obtener detecciones
        detections = camera_manager.get_camera_detections(str(camera_id), limit=limit)
        
        # Obtener estadísticas
        stats = camera_manager.get_detection_statistics(str(camera_id))
        
        # Obtener frame si se solicita
        frame_data = None
        if with_boxes:
            frame_data = camera_manager.get_camera_frame(str(camera_id), with_boxes=True)
            if frame_data:
                # Convertir a base64 para JSON
                import base64
                frame_base64 = base64.b64encode(frame_data).decode('utf-8')
        
        response_data = {
            'camera_id': camera_id,
            'detections': detections,
            'statistics': stats,
            'count': len(detections),
            'timestamp': datetime.now().isoformat()
        }
        
        if with_boxes and frame_data:
            response_data['frame_with_boxes'] = frame_base64
            response_data['frame_format'] = 'image/jpeg;base64'
        
        return Response(response_data)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def yolo_frame(request, camera_id):
    """Obtener frame con bounding boxes"""
    try:
        with_boxes = request.GET.get('boxes', 'true').lower() == 'true'
        
        frame_data = camera_manager.get_camera_frame(str(camera_id), with_boxes=with_boxes)
        
        if frame_data:
            from django.http import HttpResponse
            response = HttpResponse(frame_data, content_type='image/jpeg')
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            return response
        else:
            return Response({'error': 'No frame available'}, 
                          status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        return Response({'error': str(e)}, 
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def sync_yolo_to_db(request):
    """Sincronizar detecciones YOLO a base de datos"""
    try:
        data = request.data
        camera_id = data.get('camera_id')
        
        if not camera_id:
            return Response({'error': 'camera_id is required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener detecciones recientes de YOLO
        detections = camera_manager.get_camera_detections(str(camera_id), limit=50)
        
        # Guardar en base de datos
        saved_count = 0
        for detection in detections:
            try:
                # Buscar o crear cámara en DB
                camera_obj, created = Camera.objects.get_or_create(
                    id=camera_id,
                    defaults={
                        'name': f'Camera_{camera_id}',
                        'stream_url': f'http://youtube.com/watch?v={camera_id}',
                        'is_active': True
                    }
                )
                
                # Crear registro de detección
                DetectionRecord.objects.create(
                    camera=camera_obj,
                    person_count=1,  # Cada detección es una persona
                    occupancy_rate=100,  # Placeholder
                    confidence=detection.get('confidence', 0.5),
                    timestamp=datetime.fromisoformat(detection.get('timestamp')),
                    metadata=json.dumps(detection)
                )
                
                saved_count += 1
                
            except Exception as e:
                print(f"Error saving detection: {e}")
                continue
        
        return Response({
            'message': f'Synced {saved_count} detections to database',
            'camera_id': camera_id,
            'saved_count': saved_count,
            'total_detections': len(detections)
        })
        
    except Exception as e:
        return Response({'error': str(e)}, 
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)