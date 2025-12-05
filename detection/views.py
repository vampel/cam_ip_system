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
from datetime import datetime
from urllib.parse import urlparse

# Camera manager
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
                except: pass

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

            status.update({
                'original_name': cam_data['original_name'],
                'sanitized_name': name,
                'stream_url': cam_data['stream_url'],
                'clean_url': cam_data['stream_url'].replace('http://',''),
                'recent_detections': detections,
                'detection_count': len(detections),
                'detection_stats': stats
            })
            cameras_info.append(status)
        except Exception as e:
            print("Error:", e)
            continue

    return render(request, 'detection/dashboard.html', {'cameras': cameras_info})

# ============================================================
# Web Controls (HTML)
# ============================================================

@login_required
@csrf_exempt
def add_camera_view(request):
    if request.method == 'POST':
        original = request.POST.get('camera_name')
        url = request.POST.get('stream_url')

        if not original or not url:
            messages.error(request, 'Nombre y URL son requeridos')
            return redirect('dashboard')

        sanitized = sanitize_camera_name(original)
        final_url = normalize_stream_url(url)

        # evitar duplicados
        if any(c['sanitized_name'] == sanitized for c in request.session['user_cameras']):
            messages.error(request, 'Cámara ya existente')
            return redirect('dashboard')

        camera_manager.add_camera(sanitized, final_url)

        request.session['user_cameras'].append({
            'original_name': original,
            'sanitized_name': sanitized,
            'stream_url': final_url
        })
        request.session.modified = True

        messages.success(request, 'Cámara agregada')
    return redirect('dashboard')

@login_required
@csrf_exempt
def remove_camera_view(request, camera_id):
    if request.method == 'POST':
        try:
            camera_manager.stop_camera(camera_id)
            camera_manager.remove_camera(camera_id)
        except: pass

        request.session['user_cameras'] = [
            c for c in request.session['user_cameras']
            if c['sanitized_name'] != camera_id
        ]
        request.session.modified = True

        messages.success(request, 'Cámara eliminada')
    return redirect('dashboard')

@login_required
@csrf_exempt
def start_camera_view(request, camera_id):
    """ ← ESTA ERA LA FUNCIÓN FALTANTE """
    try:
        camera_manager.start_camera(camera_id)
        return JsonResponse({'success': True, 'message': f'Cámara {camera_id} iniciada'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@csrf_exempt
def stop_camera_view(request, camera_id):
    try:
        camera_manager.stop_camera(camera_id)
        return JsonResponse({'success': True, 'message': f'Cámara {camera_id} detenida'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def camera_status_view(request, camera_id):
    status = camera_manager.get_camera_status(camera_id)
    if not status:
        return JsonResponse({'error': 'No encontrada'}, status=404)
    return JsonResponse(status)

@login_required
def camera_frame_view(request, camera_id):
    frame = camera_manager.get_camera_frame(camera_id, with_boxes=True)
    if frame:
        return HttpResponse(frame, content_type='image/jpeg')
    return HttpResponse(status=404)

@login_required
def camera_detections_view(request, camera_id):
    detections = camera_manager.get_camera_detections(camera_id, limit=20)
    return JsonResponse({'camera_id': camera_id, 'detections': detections})

@login_required
def all_cameras_view(request):
    info = camera_manager.get_cameras_info()
    return JsonResponse({'cameras': info})

# ============================================================
# Streaming
# ============================================================

def video_feed(request, camera_id):
    def generate():
        while True:
            data = camera_manager.get_camera_status(camera_id)
            if data and data.get('last_frame') is not None:
                ok, buffer = cv2.imencode('.jpg', data['last_frame'], [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ok:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                           buffer.tobytes() + b'\r\n')
            time.sleep(0.1)

    return StreamingHttpResponse(generate(),
        content_type='multipart/x-mixed-replace; boundary=frame')

# ============================================================
# YOLO Test Page
# ============================================================

@login_required
def yolo_test_view(request, camera_id):
    status = camera_manager.get_camera_status(camera_id)
    if not status:
        messages.error(request, 'Cámara no encontrada')
        return redirect('dashboard')

    detections = camera_manager.get_camera_detections(camera_id, limit=20)
    stats = camera_manager.get_detection_statistics(camera_id)

    return render(request, 'detection/yolo_test.html', {
        'camera': status,
        'recent_detections': detections,
        'detection_stats': stats,
        'camera_name': camera_id
    })
# ============================================================
# Web Controls (FUNCIONES FALTANTES)
# ============================================================

@login_required
@csrf_exempt
def add_camera_web(request):
    """Agregar cámara desde el dashboard web"""
    if request.method == 'POST':
        camera_name = request.POST.get('camera_name', '').strip()
        stream_url = request.POST.get('stream_url', '').strip()
        camera_user = request.POST.get('camera_user', 'admin')
        camera_password = request.POST.get('camera_password', 'admin123')
        
        if not camera_name or not stream_url:
            messages.error(request, 'Nombre y URL son requeridos')
            return redirect('dashboard')
        
        sanitized = sanitize_camera_name(camera_name)
        final_url = normalize_stream_url(stream_url)
        
        # Evitar duplicados
        if 'user_cameras' not in request.session:
            request.session['user_cameras'] = []
        
        if any(c['sanitized_name'] == sanitized for c in request.session['user_cameras']):
            messages.error(request, f'La cámara "{camera_name}" ya existe')
            return redirect('dashboard')
        
        # Agregar cámara al manager
        camera_manager.add_camera(sanitized, final_url)
        
        # Guardar en sesión
        request.session['user_cameras'].append({
            'original_name': camera_name,
            'sanitized_name': sanitized,
            'stream_url': final_url,
            'username': camera_user,
            'password': camera_password
        })
        request.session.modified = True
        
        messages.success(request, f'Cámara "{camera_name}" agregada correctamente')
        return redirect('dashboard')
    
    return redirect('dashboard')

@login_required
@csrf_exempt
def control_camera_web(request, camera_sanitized_name):
    """Controlar una cámara específica (iniciar/detener)"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'start':
            try:
                camera_manager.start_camera(camera_sanitized_name)
                messages.success(request, f'Cámara "{camera_sanitized_name}" iniciada')
            except Exception as e:
                messages.error(request, f'Error al iniciar cámara: {str(e)}')
        
        elif action == 'stop':
            try:
                camera_manager.stop_camera(camera_sanitized_name)
                messages.success(request, f'Cámara "{camera_sanitized_name}" detenida')
            except Exception as e:
                messages.error(request, f'Error al detener cámara: {str(e)}')
    
    return redirect('dashboard')

@login_required
@csrf_exempt
def control_all_web(request):
    """Controlar todas las cámaras (iniciar/detener todas)"""
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
                    print(f"Error iniciando {cam['sanitized_name']}: {e}")
            
            messages.success(request, f'{started} cámaras iniciadas correctamente')
        
        elif action == 'stop':
            stopped = 0
            for cam in request.session['user_cameras']:
                try:
                    camera_manager.stop_camera(cam['sanitized_name'])
                    stopped += 1
                except Exception as e:
                    print(f"Error deteniendo {cam['sanitized_name']}: {e}")
            
            messages.success(request, f'{stopped} cámaras detenidas correctamente')
    
    return redirect('dashboard')