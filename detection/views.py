# detection/views.py - VERSIÓN COMPLETA CON STREAMING
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json
import re
import time
from datetime import datetime

from .camera_manager import camera_manager

# ============================================================
# Helpers
# ============================================================

def sanitize_camera_name(name):
    if not name or not name.strip():
        return "camara_sin_nombre"
    name = re.sub(r'[^\w\s-]', '', name.strip())
    name = re.sub(r'[-\s]+', '_', name)
    return name.lower() or "camara_sin_nombre"

def normalize_stream_url(url):
    if not url:
        return url
    url = url.strip()
    if url.startswith(('http://', 'https://', 'rtsp://')):
        return url
    return 'http://' + url

# ============================================================
# Auth Views
# ============================================================

def login_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'detection/login.html')

@csrf_exempt
def login_submit(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            auth_login(request, user)
            request.session['user_cameras'] = []
            return redirect('dashboard')
        return render(request, 'detection/login.html', {'error': 'Credenciales incorrectas'})
    return redirect('login_page')

def logout_view(request):
    if 'user_cameras' in request.session:
        for cam in request.session['user_cameras']:
            name = cam.get('sanitized_name')
            if name:
                try:
                    camera_manager.stop_camera(name)
                    camera_manager.remove_camera(name)
                except: 
                    pass
    auth_logout(request)
    messages.success(request, 'Sesión cerrada')
    return redirect('login_page')

# ============================================================
# Dashboard
# ============================================================

@login_required
def dashboard(request):
    if 'user_cameras' not in request.session:
        request.session['user_cameras'] = []

    cameras_info = []
    for cam_data in request.session['user_cameras']:
        try:
            name = cam_data.get('sanitized_name')
            if not name:
                continue

            status = camera_manager.get_camera_status(name)
            if not status:
                continue

            detections = camera_manager.get_camera_detections(name, limit=10)
            stats = camera_manager.get_detection_statistics(name)
            
            # Contar personas
            person_count = sum(1 for d in detections if d.get('label') == 'person')

            status.update({
                'original_name': cam_data['original_name'],
                'sanitized_name': name,
                'name': cam_data['original_name'],
                'stream_url': cam_data['stream_url'],
                'person_count': person_count,
                'recent_detections': detections,
                'detection_count': len(detections),
                'detection_stats': stats,
                'running': status.get('running', False)
            })
            cameras_info.append(status)
        except Exception as e:
            print(f"Error loading camera: {e}")
            continue

    return render(request, 'detection/dashboard.html', {'cameras': cameras_info})

# ============================================================
# Web Controls
# ============================================================

@login_required
@csrf_exempt
def add_camera_view(request):
    """Agregar cámara"""
    if request.method == 'POST':
        camera_name = request.POST.get('camera_name', '').strip()
        stream_url = request.POST.get('stream_url', '').strip()
        
        if not camera_name or not stream_url:
            messages.error(request, 'Nombre y URL son requeridos')
            return redirect('dashboard')
        
        sanitized = sanitize_camera_name(camera_name)
        final_url = normalize_stream_url(stream_url)
        
        if 'user_cameras' not in request.session:
            request.session['user_cameras'] = []
        
        if any(c['sanitized_name'] == sanitized for c in request.session['user_cameras']):
            messages.error(request, f'La cámara "{camera_name}" ya existe')
            return redirect('dashboard')
        
        camera_manager.add_camera(sanitized, final_url)
        
        request.session['user_cameras'].append({
            'original_name': camera_name,
            'sanitized_name': sanitized,
            'stream_url': final_url
        })
        request.session.modified = True
        
        messages.success(request, f'Cámara "{camera_name}" agregada correctamente')
        return redirect('dashboard')
    
    return redirect('dashboard')

@login_required
@csrf_exempt
def control_camera_web(request, camera_sanitized_name):
    """Controlar cámara (iniciar/detener)"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'start':
            try:
                camera_manager.start_camera(camera_sanitized_name)
                messages.success(request, f'Cámara iniciada')
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
        
        elif action == 'stop':
            try:
                camera_manager.stop_camera(camera_sanitized_name)
                messages.success(request, f'Cámara detenida')
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
    
    return redirect('dashboard')

@login_required
@csrf_exempt
def remove_camera_view(request, camera_sanitized_name):
    """Eliminar cámara"""
    if request.method == 'POST':
        try:
            camera_manager.stop_camera(camera_sanitized_name)
            camera_manager.remove_camera(camera_sanitized_name)
            
            user_cameras = request.session.get('user_cameras', [])
            user_cameras = [c for c in user_cameras if c.get('sanitized_name') != camera_sanitized_name]
            request.session['user_cameras'] = user_cameras
            request.session.modified = True
            
            messages.success(request, 'Cámara eliminada')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return redirect('dashboard')

@login_required
@csrf_exempt
def control_all_web(request):
    """Controlar todas las cámaras"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if 'user_cameras' not in request.session:
            request.session['user_cameras'] = []
        
        if action == 'start':
            started = 0
            for cam in request.session['user_cameras']:
                try:
                    camera_manager.start_camera(cam['sanitized_name'])
                    started += 1
                except Exception as e:
                    print(f"Error: {e}")
            messages.success(request, f'{started} cámaras iniciadas')
        
        elif action == 'stop':
            stopped = 0
            for cam in request.session['user_cameras']:
                try:
                    camera_manager.stop_camera(cam['sanitized_name'])
                    stopped += 1
                except Exception as e:
                    print(f"Error: {e}")
            messages.success(request, f'{stopped} cámaras detenidas')
    
    return redirect('dashboard')

# ============================================================
# API Views (tus funciones originales)
# ============================================================

@login_required
def all_cameras_view(request):
    """API: Listar todas las cámaras"""
    info = camera_manager.get_cameras_info()
    return JsonResponse({'cameras': info})

@login_required
@csrf_exempt
def start_camera_view(request, camera_id):
    """API: Iniciar cámara"""
    try:
        camera_manager.start_camera(camera_id)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@csrf_exempt
def stop_camera_view(request, camera_id):
    """API: Detener cámara"""
    try:
        camera_manager.stop_camera(camera_id)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def camera_status_view(request, camera_id):
    """API: Estado de cámara"""
    status = camera_manager.get_camera_status(camera_id)
    if not status:
        return JsonResponse({'error': 'No encontrada'}, status=404)
    return JsonResponse(status)

@login_required
def camera_frame_view(request, camera_id):
    """API: Frame actual"""
    frame = camera_manager.get_camera_frame(camera_id, with_boxes=True)
    if frame:
        return HttpResponse(frame, content_type='image/jpeg')
    return HttpResponse(status=404)

@login_required
def camera_detections_view(request, camera_id):
    """API: Detecciones"""
    detections = camera_manager.get_camera_detections(camera_id, limit=20)
    return JsonResponse({'camera_id': camera_id, 'detections': detections})

# ============================================================
# NUEVAS FUNCIONES - STREAMING CON YOLO BOUNDING BOXES
# ============================================================

def video_feed(request, camera_id):
    """
    Stream de video en tiempo real CON bounding boxes de YOLO
    Este endpoint retorna un stream MJPEG que el navegador puede mostrar en un <img>
    """
    def generate():
        while True:
            try:
                # Obtener frame CON bounding boxes dibujados
                frame_bytes = camera_manager.get_camera_frame(camera_id, with_boxes=True)
                
                if frame_bytes:
                    # Enviar frame en formato MJPEG
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                else:
                    # Si no hay frame, esperar un poco
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"Error en video_feed para {camera_id}: {e}")
                time.sleep(0.1)
    
    return StreamingHttpResponse(
        generate(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )

def camera_stats_api(request, camera_id):
    """
    API para obtener estadísticas en tiempo real
    JavaScript llama esto cada 2 segundos para actualizar los números
    """
    try:
        status = camera_manager.get_camera_status(camera_id)
        
        if not status:
            return JsonResponse({'error': 'Camera not found'}, status=404)
        
        # Obtener detecciones actuales
        detections = camera_manager.get_camera_detections(camera_id)
        
        # Contar personas (solo objetos de clase 'person')
        person_count = sum(1 for d in detections if d.get('label') == 'person')
        
        # Contar por tipo de objeto
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
            'yolo_enabled': status.get('yolo_enabled', False),
            'timestamp': time.time()
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)