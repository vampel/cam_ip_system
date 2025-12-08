# dashboard/views.py - TU VERSIÓN ORIGINAL + STREAMING
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
import json
import time

from detection.camera_manager import camera_manager

@csrf_exempt
def camera_detections_view(request, camera_id):
    """
    Obtener lista de detecciones REALES de una cámara
    ⚠️ SIN DATOS SIMULADOS
    """
    try:
        # Obtener detecciones REALES del CameraManager
        detections = camera_manager.get_camera_detections(camera_id, limit=20)
        
        # Obtener estadísticas REALES
        stats = camera_manager.get_detection_statistics(camera_id)
        
        return JsonResponse({
            'camera_id': camera_id,
            'detections': detections,  # ← SOLO detecciones reales de YOLO
            'count': len(detections),
            'statistics': stats,
            'yolo_enabled': stats.get('yolo_enabled', False),
            'message': 'Detecciones REALES' if stats.get('yolo_enabled') else 'YOLO no disponible - instalar ultralytics'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def add_camera_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            camera_id = data.get('camera_id')
            youtube_url = data.get('youtube_url')
            
            success = camera_manager.add_camera(camera_id, youtube_url)
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': 'Cámara agregada exitosamente'
                })
            else:
                return JsonResponse({
                    'error': 'No se pudo agregar la cámara'
                }, status=400)
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@csrf_exempt 
def start_camera_view(request, camera_id):
    if request.method == 'POST':
        success = camera_manager.start_camera(camera_id)
        return JsonResponse({'success': success})
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@csrf_exempt
def stop_camera_view(request, camera_id):
    if request.method == 'POST':
        camera_manager.stop_camera(camera_id)
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@csrf_exempt
def camera_status_view(request, camera_id):
    status = camera_manager.get_camera_status(camera_id)
    if status:
        return JsonResponse(status)
    return JsonResponse({'error': 'Cámara no encontrada'}, status=404)

def camera_frame_view(request, camera_id):
    """Retorna frame REAL de la cámara (con o sin bounding boxes)"""
    with_boxes = request.GET.get('boxes', 'true').lower() == 'true'
    
    frame_data = camera_manager.get_camera_frame(camera_id, with_boxes=with_boxes)
    
    if frame_data:
        return HttpResponse(frame_data, content_type='image/jpeg')
    
    # Si no hay frame, retornar error (NO imagen placeholder)
    return HttpResponse(status=404)

@csrf_exempt
def remove_camera_view(request, camera_id):
    if request.method == 'POST':
        camera_manager.remove_camera(camera_id)
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Método no permitido'}, status=405)

def all_cameras_view(request):
    """Lista de todas las cámaras con información REAL"""
    cameras = camera_manager.get_cameras_info()
    return JsonResponse({
        'cameras': cameras,
        'total': len(cameras)
    })

def dashboard_view(request):
    return render(request, 'dashboard/index.html')


# ============================================================
# NUEVAS FUNCIONES PARA STREAMING (NO TOCAN LAS ANTERIORES)
# ============================================================

def video_feed(request, camera_id):
    """
    Stream de video CON bounding boxes de YOLO
    URL: /dashboard/stream/<camera_id>/
    """
    def generate():
        while True:
            try:
                frame_bytes = camera_manager.get_camera_frame(camera_id, with_boxes=True)
                
                if frame_bytes:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"Error en video_feed: {e}")
                time.sleep(0.1)
    
    return StreamingHttpResponse(
        generate(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )


def camera_stats_api(request, camera_id):
    """
    API para stats en tiempo real (para actualizar números sin refrescar)
    URL: /dashboard/api/<camera_id>/stats/
    """
    try:
        status = camera_manager.get_camera_status(camera_id)
        
        if not status:
            return JsonResponse({'error': 'Camera not found'}, status=404)
        
        detections = camera_manager.get_camera_detections(camera_id)
        
        # Contar personas
        person_count = sum(1 for d in detections if d.get('label') == 'person')
        
        # Contar por tipo
        object_counts = {}
        for d in detections:
            label = d.get('label', 'unknown')
            object_counts[label] = object_counts.get(label, 0) + 1
        
        return JsonResponse({
            'camera_id': camera_id,
            'running': status.get('running', False),
            'fps': status.get('fps', 0),
            'total_detections': len(detections),
            'person_count': person_count,
            'object_counts': object_counts,
            'timestamp': time.time()
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)