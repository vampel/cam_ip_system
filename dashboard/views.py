# views.py
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
import json

from detection.camera_manager import camera_manager

@csrf_exempt
def camera_detections_view(request, camera_id):
    """Obtener lista de detecciones de una cámara"""
    try:
        # Aquí obtienes las detecciones reales de tu CameraManager
        # Por ahora devolvemos datos de ejemplo
        import random
        from datetime import datetime, timedelta
        
        detections = []
        now = datetime.now()
        
        for i in range(random.randint(1, 8)):
            detections.append({
                'id': f'det_{camera_id}_{i}',
                'timestamp': (now - timedelta(minutes=random.randint(1, 30))).isoformat(),
                'confidence': round(0.6 + random.random() * 0.4, 3),
                'area': random.randint(5000, 20000),
                'x': random.randint(0, 640),
                'y': random.randint(0, 360),
                'width': random.randint(40, 120),
                'height': random.randint(80, 200)
            })
        
        return JsonResponse({
            'camera_id': camera_id,
            'detections': detections,
            'count': len(detections)
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
    frame_data = camera_manager.get_camera_frame(camera_id)
    if frame_data:
        return HttpResponse(frame_data, content_type='image/jpeg')
    
    # Imagen por defecto
    import cv2
    import numpy as np
    default_frame = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(default_frame, f'Camera: {camera_id}', (50, 180), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    _, buffer = cv2.imencode('.jpg', default_frame)
    return HttpResponse(buffer.tobytes(), content_type='image/jpeg')

@csrf_exempt
def remove_camera_view(request, camera_id):
    if request.method == 'POST':
        camera_manager.remove_camera(camera_id)
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Método no permitido'}, status=405)

def all_cameras_view(request):
    cameras = camera_manager.get_cameras_info()
    return JsonResponse({'cameras': cameras})

def dashboard_view(request):
    return render(request, 'dashboard/index.html')