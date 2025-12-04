# detection/views.py
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json
import cv2
import re
import time
import numpy as np
from datetime import datetime, timedelta
from urllib.parse import urlparse

# Importar CameraManager actualizado
from .camera_manager import camera_manager

def sanitize_camera_name(name):
    """Sanitizar nombre de cámara para usar en URLs"""
    if not name or not name.strip():
        return "camara_sin_nombre"
    
    name = re.sub(r'[^\w\s-]', '', name.strip())
    name = re.sub(r'[-\s]+', '_', name)
    
    if not name:
        return "camara_sin_nombre"
    
    return name.lower()

def normalize_stream_url(url):
    """Normalizar URL de stream - agregar http:// si falta"""
    if not url:
        return url
    
    url = url.strip()
    
    # Si ya tiene protocolo, retornar
    if url.startswith(('http://', 'https://', 'rtsp://')):
        return url
    
    # Si es solo IP o dominio, agregar http://
    url = 'http://' + url
    
    return url

# ========== VISTAS DE AUTENTICACIÓN ==========

def login_page(request):
    """Página de login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'detection/login.html')

@csrf_exempt
def login_submit(request):
    """Procesar login desde formulario HTML"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            request.session['user_cameras'] = []
            return redirect('dashboard')
        else:
            return render(request, 'detection/login.html', {
                'error': 'Usuario o contraseña incorrectos'
            })
    
    return redirect('login_page')

def logout_view(request):
    """Cerrar sesión"""
    if 'user_cameras' in request.session:
        for camera_data in request.session['user_cameras']:
            try:
                sanitized_name = camera_data.get('sanitized_name', '')
                if sanitized_name:
                    camera_manager.stop_camera(sanitized_name)
                    camera_manager.remove_camera(sanitized_name)
            except:
                pass
        del request.session['user_cameras']
    
    auth_logout(request)
    messages.success(request, 'Sesión cerrada correctamente')
    return redirect('login_page')

# ========== VISTAS PROTEGIDAS ==========

@login_required
def dashboard(request):
    """Dashboard principal con detecciones YOLO"""
    if 'user_cameras' not in request.session:
        request.session['user_cameras'] = []
    
    cameras_info = []
    for camera_data in request.session['user_cameras']:
        try:
            sanitized_name = camera_data.get('sanitized_name', '')
            if sanitized_name:
                camera_status = camera_manager.get_camera_status(sanitized_name)
                if camera_status:
                    # Obtener detecciones recientes
                    recent_detections = camera_manager.get_camera_detections(sanitized_name, limit=10)
                    
                    camera_status['original_name'] = camera_data.get('original_name', 'Cámara Sin Nombre')
                    camera_status['sanitized_name'] = sanitized_name
                    camera_status['stream_url'] = camera_data.get('stream_url', '')
                    camera_status['username'] = camera_data.get('username')
                    camera_status['password'] = camera_data.get('password')
                    
                    # Limpiar URL para mostrar en template
                    clean_url = camera_status['stream_url'].replace('http://', '').replace('https://', '')
                    camera_status['clean_url'] = clean_url
                    
                    # Agregar detecciones
                    camera_status['recent_detections'] = recent_detections
                    camera_status['detection_count'] = len(recent_detections)
                    
                    # Obtener estadísticas
                    stats = camera_manager.get_detection_statistics(sanitized_name)
                    camera_status['detection_stats'] = stats
                    
                    cameras_info.append(camera_status)
        except Exception as e:
            print(f"Error procesando cámara: {e}")
            continue
    
    return render(request, 'detection/dashboard.html', {
        'cameras': cameras_info
    })

@login_required
@csrf_exempt
def add_camera_web(request):
    """Agregar cámara"""
    if request.method == 'POST':
        original_name = request.POST.get('camera_name', '').strip()
        stream_url = request.POST.get('stream_url', '').strip()
        username = request.POST.get('camera_user', '').strip() or None
        password = request.POST.get('camera_password', '').strip() or None
        
        if not original_name or not stream_url:
            messages.error(request, 'Nombre y URL son requeridos')
            return redirect('dashboard')
        
        try:
            sanitized_name = sanitize_camera_name(original_name)
            normalized_url = normalize_stream_url(stream_url)
            
            existing_cameras = request.session.get('user_cameras', [])
            if any(cam.get('sanitized_name') == sanitized_name for cam in existing_cameras):
                messages.error(request, f'La cámara "{original_name}" ya existe')
                return redirect('dashboard')
            
            # Agregar cámara al manager (usando URL de YouTube)
            camera_manager.add_camera(sanitized_name, normalized_url)
            
            existing_cameras.append({
                'original_name': original_name,
                'sanitized_name': sanitized_name,
                'stream_url': normalized_url,
                'username': username,
                'password': password
            })
            request.session['user_cameras'] = existing_cameras
            request.session.modified = True
            
            messages.success(request, f'Cámara "{original_name}" agregada correctamente')
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return redirect('dashboard')

@login_required
@csrf_exempt
def control_camera_web(request, camera_sanitized_name):
    """Controlar cámara individual"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        try:
            if action == 'start':
                camera_manager.start_camera(camera_sanitized_name)
                messages.success(request, 'Cámara iniciada')
            elif action == 'stop':
                camera_manager.stop_camera(camera_sanitized_name)
                messages.success(request, 'Cámara detenida')
            elif action == 'clear_detections':
                camera_manager.clear_detections(camera_sanitized_name)
                messages.success(request, 'Detecciones limpiadas')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return redirect('dashboard')

@login_required
@csrf_exempt
def control_all_web(request):
    """Controlar todas las cámaras"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        try:
            if action == 'start':
                camera_manager.start_all_cameras()
                messages.success(request, 'Todas las cámaras iniciadas')
            elif action == 'stop':
                camera_manager.stop_all_cameras()
                messages.success(request, 'Todas las cámaras detenidas')
            elif action == 'clear_all_detections':
                # Limpiar detecciones de todas las cámaras
                user_cameras = request.session.get('user_cameras', [])
                for camera_data in user_cameras:
                    sanitized_name = camera_data.get('sanitized_name')
                    if sanitized_name:
                        camera_manager.clear_detections(sanitized_name)
                messages.success(request, 'Todas las detecciones limpiadas')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return redirect('dashboard')

@login_required
@csrf_exempt
def remove_camera_web(request, camera_sanitized_name):
    """Eliminar cámara"""
    if request.method == 'POST':
        try:
            camera_manager.stop_camera(camera_sanitized_name)
            camera_manager.remove_camera(camera_sanitized_name)
            
            user_cameras = request.session.get('user_cameras', [])
            user_cameras = [cam for cam in user_cameras if cam.get('sanitized_name') != camera_sanitized_name]
            request.session['user_cameras'] = user_cameras
            request.session.modified = True
            
            messages.success(request, 'Cámara eliminada')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return redirect('dashboard')

# ========== APIs PÚBLICAS ==========

def health_check(request):
    return JsonResponse({
        'status': 'healthy',
        'service': 'Camera Detection System API',
        'yolo_version': '8.0',
        'timestamp': datetime.now().isoformat()
    })

def video_feed(request, camera_sanitized_name):
    """Stream de video optimizado"""
    def generate_frames():
        while True:
            camera_status = camera_manager.get_camera_status(camera_sanitized_name)
            if camera_status and camera_status.get('last_frame') is not None:
                frame = camera_status['last_frame']
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.1)
    
    return StreamingHttpResponse(
        generate_frames(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )

# ========== NUEVAS APIS PARA DETECCIONES YOLO ==========

def camera_detections_api(request, camera_sanitized_name):
    """API para obtener detecciones reales de YOLO"""
    try:
        limit = int(request.GET.get('limit', 20))
        include_history = request.GET.get('history', 'false').lower() == 'true'
        
        # Obtener detecciones recientes
        recent_detections = camera_manager.get_camera_detections(camera_sanitized_name, limit=limit)
        
        # Opcionalmente incluir historial
        if include_history:
            history = camera_manager.get_detection_history(camera_sanitized_name, limit=50)
        else:
            history = []
        
        # Obtener estadísticas
        stats = camera_manager.get_detection_statistics(camera_sanitized_name)
        
        return JsonResponse({
            'camera_id': camera_sanitized_name,
            'recent_detections': recent_detections,
            'detection_history': history,
            'statistics': stats,
            'count': len(recent_detections),
            'timestamp': datetime.now().isoformat(),
            'success': True
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)

def camera_frame_api(request, camera_sanitized_name):
    """API para obtener frame de cámara (con o sin bounding boxes)"""
    try:
        # Verificar si se quieren bounding boxes
        with_boxes = request.GET.get('boxes', 'false').lower() == 'true'
        
        # Obtener frame del camera_manager
        frame_data = camera_manager.get_camera_frame(camera_sanitized_name, with_boxes=with_boxes)
        
        if frame_data:
            return HttpResponse(frame_data, content_type='image/jpeg')
        else:
            # Crear imagen por defecto
            frame = np.zeros((360, 640, 3), dtype=np.uint8)
            cv2.putText(frame, f'Camera: {camera_sanitized_name}', (50, 180), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            if with_boxes:
                cv2.putText(frame, 'Bounding Boxes', (50, 220), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                cv2.putText(frame, 'Original View', (50, 220), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
            
            _, buffer = cv2.imencode('.jpg', frame)
            return HttpResponse(buffer.tobytes(), content_type='image/jpeg')
            
    except Exception as e:
        # Imagen de error
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(frame, f'Error: {str(e)[:50]}', (50, 180), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        _, buffer = cv2.imencode('.jpg', frame)
        return HttpResponse(buffer.tobytes(), content_type='image/jpeg')

def camera_status_api(request, camera_sanitized_name):
    """API para obtener estado completo de cámara"""
    try:
        camera_status = camera_manager.get_camera_status(camera_sanitized_name)
        
        if not camera_status:
            return JsonResponse({
                'error': 'Camera not found',
                'success': False
            }, status=404)
        
        # Agregar información adicional
        recent_detections = camera_manager.get_camera_detections(camera_sanitized_name, limit=10)
        stats = camera_manager.get_detection_statistics(camera_sanitized_name)
        
        camera_status['recent_detections'] = recent_detections
        camera_status['detection_statistics'] = stats
        camera_status['timestamp'] = datetime.now().isoformat()
        camera_status['success'] = True
        
        return JsonResponse(camera_status)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)

def all_cameras_api(request):
    """API para obtener todas las cámaras"""
    try:
        cameras_info = camera_manager.get_cameras_info()
        
        # Agregar detecciones a cada cámara
        for camera in cameras_info:
            camera_id = camera['id']
            camera['recent_detections'] = camera_manager.get_camera_detections(camera_id, limit=5)
            camera['has_boxes'] = camera_manager.get_camera_frame(camera_id, with_boxes=True) is not None
        
        return JsonResponse({
            'cameras': cameras_info,
            'count': len(cameras_info),
            'timestamp': datetime.now().isoformat(),
            'success': True
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)

@csrf_exempt
def add_camera_api(request):
    """API para agregar cámara"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            camera_id = data.get('camera_id')
            youtube_url = data.get('youtube_url')
            
            if not camera_id or not youtube_url:
                return JsonResponse({
                    'error': 'camera_id and youtube_url are required',
                    'success': False
                }, status=400)
            
            success = camera_manager.add_camera(camera_id, youtube_url)
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': f'Camera {camera_id} added successfully',
                    'camera_id': camera_id
                })
            else:
                return JsonResponse({
                    'error': 'Failed to add camera',
                    'success': False
                }, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON',
                'success': False
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'success': False
            }, status=500)
    
    return JsonResponse({
        'error': 'Method not allowed',
        'success': False
    }, status=405)

@csrf_exempt
def start_camera_api(request, camera_id):
    """API para iniciar cámara"""
    if request.method == 'POST':
        try:
            success = camera_manager.start_camera(camera_id)
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': f'Camera {camera_id} started'
                })
            else:
                return JsonResponse({
                    'error': f'Failed to start camera {camera_id}',
                    'success': False
                }, status=400)
        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'success': False
            }, status=500)
    
    return JsonResponse({
        'error': 'Method not allowed',
        'success': False
    }, status=405)

@csrf_exempt
def stop_camera_api(request, camera_id):
    """API para detener cámara"""
    if request.method == 'POST':
        try:
            camera_manager.stop_camera(camera_id)
            return JsonResponse({
                'success': True,
                'message': f'Camera {camera_id} stopped'
            })
        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'success': False
            }, status=500)
    
    return JsonResponse({
        'error': 'Method not allowed',
        'success': False
    }, status=405)

@csrf_exempt
def remove_camera_api(request, camera_id):
    """API para eliminar cámara"""
    if request.method == 'POST':
        try:
            camera_manager.remove_camera(camera_id)
            return JsonResponse({
                'success': True,
                'message': f'Camera {camera_id} removed'
            })
        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'success': False
            }, status=500)
    
    return JsonResponse({
        'error': 'Method not allowed',
        'success': False
    }, status=405)

# ========== VISTA PARA PRUEBAS YOLO ==========

@login_required
def yolo_test_view(request, camera_sanitized_name):
    """Vista especial para ver detecciones YOLO en tiempo real"""
    try:
        camera_status = camera_manager.get_camera_status(camera_sanitized_name)
        if not camera_status:
            messages.error(request, 'Cámara no encontrada')
            return redirect('dashboard')
        
        # Obtener detecciones recientes
        recent_detections = camera_manager.get_camera_detections(camera_sanitized_name, limit=20)
        detection_stats = camera_manager.get_detection_statistics(camera_sanitized_name)
        
        return render(request, 'detection/yolo_test.html', {
            'camera': camera_status,
            'recent_detections': recent_detections,
            'detection_stats': detection_stats,
            'camera_name': camera_sanitized_name
        })
        
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('dashboard')