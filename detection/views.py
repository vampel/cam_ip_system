from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json
import cv2
import re
from urllib.parse import urlparse
from .camera_manager import CameraManager

# CameraManager global
camera_manager = CameraManager()

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
    if not url.startswith(('http://', 'https://', 'rtsp://')):
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
            # Inicializar sesión vacía
            request.session['user_cameras'] = []
            return redirect('dashboard')
        else:
            return render(request, 'detection/login.html', {
                'error': 'Usuario o contraseña incorrectos'
            })
    
    return redirect('login_page')

def logout_view(request):
    """Cerrar sesión - Vista personalizada"""
    # Limpiar cámaras antes de logout
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
    
    # Hacer logout
    auth_logout(request)
    messages.success(request, 'Sesión cerrada correctamente')
    return redirect('login_page')

# ========== VISTAS PROTEGIDAS ==========

@login_required
def dashboard(request):
    """Dashboard principal después del login"""
    # Inicializar sesión si no existe
    if 'user_cameras' not in request.session:
        request.session['user_cameras'] = []
    
    # Obtener información de cámaras
    cameras_info = []
    for camera_data in request.session['user_cameras']:
        try:
            sanitized_name = camera_data.get('sanitized_name', '')
            if sanitized_name:
                camera_status = camera_manager.get_camera_status(sanitized_name)
                if camera_status:
                    camera_status['original_name'] = camera_data.get('original_name', 'Cámara Sin Nombre')
                    camera_status['sanitized_name'] = sanitized_name
                    camera_status['stream_url'] = camera_data.get('stream_url', '')
                    camera_status['username'] = camera_data.get('username')
                    camera_status['password'] = camera_data.get('password')
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
    """Agregar cámara desde formulario web"""
    if request.method == 'POST':
        original_name = request.POST.get('camera_name', '').strip()
        stream_url = request.POST.get('stream_url', '').strip()
        username = request.POST.get('camera_user', '').strip() or None
        password = request.POST.get('camera_password', '').strip() or None
        
        if not original_name or not stream_url:
            messages.error(request, 'Nombre y URL son requeridos')
            return redirect('dashboard')
        
        try:
            # Sanitizar y normalizar
            sanitized_name = sanitize_camera_name(original_name)
            normalized_url = normalize_stream_url(stream_url)
            
            # Verificar si ya existe
            existing_cameras = request.session.get('user_cameras', [])
            if any(cam.get('sanitized_name') == sanitized_name for cam in existing_cameras):
                messages.error(request, f'La cámara "{original_name}" ya existe')
                return redirect('dashboard')
            
            # Agregar al manager (SOLO 2 argumentos)
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
            
            # Remover de sesión
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
        'service': 'Camera IP System API'
    })

def video_feed(request, camera_sanitized_name):
    """Stream de video"""
    # Buscar la cámara en la sesión para obtener credenciales
    camera_data = None
    for cam in request.session.get('user_cameras', []):
        if cam.get('sanitized_name') == camera_sanitized_name:
            camera_data = cam
            break
    
    if not camera_data:
        return JsonResponse({'error': 'Camera not found'}, status=404)
    
    def generate_frames():
        # Usar las credenciales si están disponibles
        stream_url = camera_data['stream_url']
        username = camera_data.get('username')
        password = camera_data.get('password')
        
        # Si hay credenciales, construir URL con autenticación
        if username and password:
            # Para HTTP básico: http://usuario:contraseña@ip/path
            parsed_url = urlparse(stream_url)
            auth_url = f"{parsed_url.scheme}://{username}:{password}@{parsed_url.netloc}{parsed_url.path}"
            if parsed_url.query:
                auth_url += f"?{parsed_url.query}"
            cap = cv2.VideoCapture(auth_url)
        else:
            cap = cv2.VideoCapture(stream_url)
            
        while True:
            success, frame = cap.read()
            if not success:
                break
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        cap.release()
    
    return StreamingHttpResponse(
        generate_frames(), 
        content_type='multipart/x-mixed-replace; boundary=frame'
    )