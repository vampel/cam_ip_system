# detection/camera_manager.py
import cv2
import threading
import time
from datetime import datetime
from ultralytics import YOLO
import numpy as np
import subprocess
import tempfile
import os
import signal
import re
import sys
import json

# Importar el extractor
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from detection.youtube_utils import YouTubeStreamExtractor

class CameraManager:
    def __init__(self):
        self.cameras = {}
        self.model = YOLO('yolov8n.pt')
        self.lock = threading.Lock()
        self.extractor = YouTubeStreamExtractor()
        print("✅ CameraManager inicializado con YouTube support y YOLO")
    
    def add_camera(self, camera_id, youtube_url):
        """Agregar cámara desde URL de YouTube"""
        with self.lock:
            # Extraer video ID
            video_id = self._extract_video_id(youtube_url)
            if not video_id:
                print(f"❌ URL de YouTube inválida: {youtube_url}")
                return False
            
            print(f"🔍 Obteniendo stream para video ID: {video_id}")
            
            # Obtener URL directa del stream
            stream_url = self.extractor.get_youtube_stream_url(
                f"https://www.youtube.com/watch?v={video_id}"
            )
            
            if not stream_url:
                print(f"❌ No se pudo obtener stream para {video_id}")
                return False
            
            print(f"✅ Stream obtenido: {stream_url[:80]}...")
            
            self.cameras[camera_id] = {
                'youtube_url': f"https://www.youtube.com/watch?v={video_id}",
                'stream_url': stream_url,  # URL directa del stream
                'video_id': video_id,
                'status': 'stopped',
                'thread': None,
                'person_count': 0,
                'last_detections': [],      # Lista de detecciones recientes
                'last_update': None,
                'last_frame': None,         # Frame original
                'last_frame_with_boxes': None,  # Frame con bounding boxes
                'cap': None,  # Objeto VideoCapture
                'fps': 5,     # FPS para procesamiento
                'width': 640,
                'height': 360,
                'detection_history': []     # Historial de detecciones
            }
            print(f"✅ Cámara '{camera_id}' agregada exitosamente")
            return True
    
    def _extract_video_id(self, url):
        """Extraer video ID de diferentes formatos de URL de YouTube"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtube\.com/embed/|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'^([a-zA-Z0-9_-]{11})$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def start_camera(self, camera_id):
        """Iniciar procesamiento de cámara"""
        with self.lock:
            if camera_id not in self.cameras:
                print(f"❌ Cámara '{camera_id}' no encontrada")
                return False
            
            camera = self.cameras[camera_id]
            
            if camera['status'] == 'running':
                print(f"ℹ️ Cámara '{camera_id}' ya está ejecutándose")
                return True
            
            camera['status'] = 'starting'
            
            # Crear thread
            thread = threading.Thread(target=self._process_stream, args=(camera_id,))
            camera['thread'] = thread
            thread.daemon = True
            thread.start()
            
            print(f"🔄 Iniciando cámara '{camera_id}'...")
            return True
    
    def _process_stream(self, camera_id):
        """Procesar stream de video con detección YOLO en tiempo real"""
        with self.lock:
            if camera_id not in self.cameras:
                return
            camera = self.cameras[camera_id]
        
        stream_url = camera['stream_url']
        
        print(f"🎬 Conectando a stream: {camera_id}")
        print(f"   URL: {stream_url[:100]}...")
        
        # Intentar abrir el stream con OpenCV
        cap = cv2.VideoCapture(stream_url)
        
        # Configurar propiedades
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        if not cap.isOpened():
            print(f"❌ No se pudo abrir stream para {camera_id}")
            with self.lock:
                if camera_id in self.cameras:
                    self.cameras[camera_id]['status'] = 'error'
            return
        
        with self.lock:
            if camera_id in self.cameras:
                self.cameras[camera_id]['status'] = 'running'
                self.cameras[camera_id]['cap'] = cap
        
        print(f"✅ Conexión establecida: {camera_id}")
        
        frame_count = 0
        last_detection_time = time.time()
        
        try:
            while True:
                with self.lock:
                    if (camera_id not in self.cameras or 
                        self.cameras[camera_id]['status'] != 'running'):
                        break
                
                # Leer frame
                ret, frame = cap.read()
                
                if not ret:
                    print(f"⚠️ No se pudo leer frame de {camera_id}, reintentando...")
                    time.sleep(1)
                    
                    # Intentar reconectar
                    cap.release()
                    cap = cv2.VideoCapture(stream_url)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    
                    if not cap.isOpened():
                        print(f"❌ Reconexión fallida para {camera_id}")
                        break
                    
                    with self.lock:
                        if camera_id in self.cameras:
                            self.cameras[camera_id]['cap'] = cap
                    
                    continue
                
                # Redimensionar frame si es necesario
                if frame.shape[1] > 640:
                    frame = cv2.resize(frame, (640, 360))
                
                # Guardar frame original
                frame_original = frame.copy()
                
                # Crear copia para dibujar bounding boxes
                frame_with_boxes = frame.copy()
                
                # Detectar personas con YOLO en cada frame
                try:
                    # Detección con YOLO
                    results = self.model(frame, verbose=False, conf=0.4)
                    
                    # Procesar detecciones
                    detections = []
                    person_count = 0
                    
                    for result in results:
                        boxes = result.boxes
                        if boxes is not None:
                            for idx, box in enumerate(boxes):
                                cls = int(box.cls[0])
                                if cls == 0:  # Person class
                                    person_count += 1
                                    
                                    # Extraer datos del bounding box
                                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                                    conf = float(box.conf[0].cpu().numpy())
                                    
                                    # Crear objeto de detección
                                    detection = {
                                        'id': f'det_{camera_id}_{person_count}_{int(time.time())}',
                                        'timestamp': datetime.now().isoformat(),
                                        'confidence': round(conf, 3),
                                        'bbox': {
                                            'x1': round(float(x1), 2),
                                            'y1': round(float(y1), 2),
                                            'x2': round(float(x2), 2),
                                            'y2': round(float(y2), 2),
                                            'width': round(float(x2 - x1), 2),
                                            'height': round(float(y2 - y1), 2),
                                            'area': round(float((x2 - x1) * (y2 - y1)), 2)
                                        },
                                        'position': {
                                            'x': round(float((x1 + x2) / 2), 2),
                                            'y': round(float((y1 + y2) / 2), 2)
                                        }
                                    }
                                    detections.append(detection)
                                    
                                    # Dibujar bounding box en el frame
                                    color = (0, 255, 0)  # Verde
                                    thickness = 2
                                    
                                    # Dibujar rectángulo
                                    cv2.rectangle(frame_with_boxes, 
                                                (int(x1), int(y1)), 
                                                (int(x2), int(y2)), 
                                                color, thickness)
                                    
                                    # Dibujar etiqueta con confianza
                                    label = f"Person: {conf:.2f}"
                                    label_size, baseline = cv2.getTextSize(label, 
                                                                          cv2.FONT_HERSHEY_SIMPLEX, 
                                                                          0.5, thickness)
                                    cv2.rectangle(frame_with_boxes,
                                                (int(x1), int(y1) - label_size[1] - 5),
                                                (int(x1) + label_size[0], int(y1)),
                                                color, -1)
                                    cv2.putText(frame_with_boxes, label,
                                                (int(x1), int(y1) - 5),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                                (255, 255, 255), thickness=1)
                    
                    # Actualizar estado con las detecciones
                    with self.lock:
                        if camera_id in self.cameras:
                            # Guardar frames
                            self.cameras[camera_id]['last_frame'] = frame_original
                            self.cameras[camera_id]['last_frame_with_boxes'] = frame_with_boxes
                            
                            # Guardar detecciones
                            self.cameras[camera_id]['person_count'] = person_count
                            self.cameras[camera_id]['last_detections'] = detections
                            self.cameras[camera_id]['last_update'] = datetime.now().isoformat()
                            
                            # Agregar al historial (máximo 100 detecciones)
                            self.cameras[camera_id]['detection_history'].extend(detections)
                            if len(self.cameras[camera_id]['detection_history']) > 100:
                                self.cameras[camera_id]['detection_history'] = \
                                    self.cameras[camera_id]['detection_history'][-100:]
                    
                    # Mostrar en consola cada 5 segundos si hay personas
                    current_time = time.time()
                    if current_time - last_detection_time >= 5.0:
                        if person_count > 0:
                            print(f"👥 {camera_id}: {person_count} personas detectadas")
                            for det in detections[:3]:  # Mostrar primeras 3 detecciones
                                print(f"   → ID: {det['id']}, Conf: {det['confidence']:.2f}, "
                                      f"Pos: ({det['position']['x']:.0f}, {det['position']['y']:.0f})")
                        last_detection_time = current_time
                        
                except Exception as e:
                    print(f"⚠️ Error en detección {camera_id}: {e}")
                    # Guardar frame original si hay error en detección
                    with self.lock:
                        if camera_id in self.cameras:
                            self.cameras[camera_id]['last_frame'] = frame_original
                            self.cameras[camera_id]['last_frame_with_boxes'] = frame_original
                
                frame_count += 1
                
                # Pequeña pausa para controlar FPS
                time.sleep(0.05)  # ~20 FPS máximo
                
        except Exception as e:
            print(f"❌ Error en procesamiento de {camera_id}: {e}")
        
        finally:
            # Limpieza
            if cap:
                cap.release()
            
            with self.lock:
                if camera_id in self.cameras:
                    self.cameras[camera_id]['status'] = 'stopped'
                    self.cameras[camera_id]['cap'] = None
                    self.cameras[camera_id]['last_frame'] = None
                    self.cameras[camera_id]['last_frame_with_boxes'] = None
            
            print(f"⏹️ Procesamiento detenido: {camera_id}")
    
    def stop_camera(self, camera_id):
        """Detener cámara"""
        with self.lock:
            if camera_id not in self.cameras:
                return
            
            camera = self.cameras[camera_id]
            camera['status'] = 'stopping'
            
            # Cerrar VideoCapture si existe
            if camera['cap']:
                camera['cap'].release()
        
        # Esperar a que el thread termine
        thread = camera.get('thread')
        if thread and thread.is_alive():
            thread.join(timeout=3)
        
        with self.lock:
            if camera_id in self.cameras:
                self.cameras[camera_id]['status'] = 'stopped'
                self.cameras[camera_id]['thread'] = None
                self.cameras[camera_id]['cap'] = None
        
        print(f"⏹️ Cámara '{camera_id}' detenida")
    
    def get_camera_status(self, camera_id):
        """Obtener estado de la cámara"""
        with self.lock:
            if camera_id in self.cameras:
                camera = self.cameras[camera_id].copy()
                # Remover objetos grandes para JSON
                if 'last_frame' in camera:
                    camera['last_frame'] = 'available' if camera['last_frame'] is not None else None
                if 'last_frame_with_boxes' in camera:
                    camera['last_frame_with_boxes'] = 'available' if camera['last_frame_with_boxes'] is not None else None
                return camera
            return None
    
    def get_camera_frame(self, camera_id, with_boxes=False):
        """Obtener último frame de la cámara"""
        with self.lock:
            if camera_id not in self.cameras:
                return None
            
            # Elegir frame con o sin bounding boxes
            if with_boxes:
                frame = self.cameras[camera_id].get('last_frame_with_boxes')
            else:
                frame = self.cameras[camera_id].get('last_frame')
            
            if frame is not None:
                # Codificar como JPEG
                ret, buffer = cv2.imencode('.jpg', frame, 
                                          [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    return buffer.tobytes()
        
        return None
    
    def get_camera_detections(self, camera_id, limit=20):
        """Obtener detecciones recientes de una cámara"""
        with self.lock:
            if camera_id in self.cameras:
                detections = self.cameras[camera_id].get('last_detections', [])
                # Ordenar por timestamp (más recientes primero)
                detections.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                return detections[:limit]
            return []
    
    def get_detection_history(self, camera_id, limit=50):
        """Obtener historial de detecciones"""
        with self.lock:
            if camera_id in self.cameras:
                history = self.cameras[camera_id].get('detection_history', [])
                # Ordenar por timestamp (más recientes primero)
                history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                return history[:limit]
            return []
    
    def get_cameras_info(self):
        """Obtener información de todas las cámaras"""
        with self.lock:
            cameras_info = []
            for camera_id, camera_data in self.cameras.items():
                detections = camera_data.get('last_detections', [])
                info = {
                    'id': camera_id,
                    'name': camera_id,
                    'video_id': camera_data.get('video_id', ''),
                    'stream_url': camera_data.get('stream_url', '')[:100] + '...',
                    'status': camera_data['status'],
                    'person_count': camera_data['person_count'],
                    'detection_count': len(detections),
                    'last_update': camera_data['last_update'],
                    'fps': camera_data.get('fps', 5),
                    'has_boxes': camera_data.get('last_frame_with_boxes') is not None
                }
                cameras_info.append(info)
            return cameras_info
    
    def clear_detections(self, camera_id):
        """Limpiar detecciones de una cámara"""
        with self.lock:
            if camera_id in self.cameras:
                self.cameras[camera_id]['last_detections'] = []
                self.cameras[camera_id]['detection_history'] = []
                print(f"🗑️ Detecciones limpiadas para {camera_id}")
                return True
            return False
    
    def get_detection_statistics(self, camera_id):
        """Obtener estadísticas de detecciones"""
        with self.lock:
            if camera_id not in self.cameras:
                return None
            
            history = self.cameras[camera_id].get('detection_history', [])
            if not history:
                return {
                    'total_detections': 0,
                    'avg_confidence': 0,
                    'detections_per_minute': 0,
                    'last_hour_count': 0
                }
            
            # Calcular estadísticas
            total_detections = len(history)
            avg_confidence = sum(d.get('confidence', 0) for d in history) / total_detections
            
            # Detecciones en la última hora
            one_hour_ago = datetime.now().timestamp() - 3600
            last_hour = [d for d in history if 
                        datetime.fromisoformat(d.get('timestamp', '2000-01-01')).timestamp() > one_hour_ago]
            
            return {
                'total_detections': total_detections,
                'avg_confidence': round(avg_confidence, 3),
                'detections_per_minute': round(len(last_hour) / 60, 2),
                'last_hour_count': len(last_hour),
                'last_detection_time': history[0].get('timestamp') if history else None
            }

# Instancia global
camera_manager = CameraManager()