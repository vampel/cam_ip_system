# detection/yolo_detector.py
import cv2
import numpy as np
from ultralytics import YOLO
import threading
import time
from datetime import datetime
import requests
from django.utils import timezone
from .youtube_utils import YouTubeStreamExtractor

class AttendanceDetector:
    def __init__(self):
        # Cargar modelo YOLO pre-entrenado
        print("🔧 Inicializando modelo YOLO...")
        self.model = YOLO('yolov8n.pt')  # Modelo nano - rápido y eficiente
        self.cameras = {}
        self.running = False
        self.detection_threads = []
        self.youtube_extractor = YouTubeStreamExtractor()
        print("✅ Modelo YOLO cargado correctamente")
    
    def add_camera(self, name, stream_url):
        """Agregar cámara ESP32 al sistema"""
        self.cameras[name] = {
            'url': stream_url,
            'person_count': 0,
            'chair_count': 0,
            'occupancy_rate': 0,
            'last_update': datetime.now(),
            'status': 'disconnected',
            'last_frame': None,
            'fps': 0
        }
        print(f"📹 Cámara '{name}' agregada: {stream_url}")
    
    def _capture_frame(self, url):
        """Capturar frame de cualquier fuente"""
        # DETECTAR si es YouTube URL
        if 'youtube.com' in url or 'youtu.be' in url:
            return self._capture_youtube_frame(url)
        else:
            # Proceso normal para otras URLs
            return self._capture_normal_frame(url)
    
    def _capture_normal_frame(self, url):
        """Capturar frame normal (HTTP/JPEG)"""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                img_array = np.frombuffer(response.content, np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                return frame
        except Exception as e:
            print(f"📷 Error capturando frame normal: {e}")
        return None
    
    def _capture_youtube_frame(self, youtube_url):
        """Capturar frame de stream YouTube"""
        try:
            # Obtener stream directo
            stream_url = self.youtube_extractor.get_youtube_stream_url(youtube_url)
            if not stream_url:
                return None
            
            # Usar OpenCV para capturar frame del stream
            cap = cv2.VideoCapture(stream_url)
            
            # Configurar timeout
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
            
            # Leer frame
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                return frame
                
        except Exception as e:
            print(f"🎥 Error capturando YouTube: {e}")
            
        return None
    
    def process_camera(self, camera_name):
        """Procesar una cámara específica con YOLO"""
        camera = self.cameras[camera_name]
        frame_count = 0
        start_time = time.time()
        
        print(f"🎬 Iniciando detección para {camera_name}")
        
        while self.running and camera_name in self.cameras:
            try:
                # Capturar frame
                frame = self._capture_frame(camera['url'])
                if frame is not None:
                    frame_count += 1
                    
                    # Ejecutar YOLO en el frame
                    results = self.model(frame, verbose=False, conf=0.5)
                    
                    # Contar personas y sillas
                    person_count = self._count_objects(results, 0)   # class 0 = person
                    chair_count = self._count_objects(results, 56)   # class 56 = chair
                    
                    # Calcular tasa de ocupación
                    occupancy_rate = person_count / chair_count if chair_count > 0 else 0
                    
                    # Calcular FPS
                    current_time = time.time()
                    if current_time - start_time >= 1.0:  # Cada segundo
                        camera['fps'] = frame_count
                        frame_count = 0
                        start_time = current_time
                    
                    # Actualizar datos de la cámara
                    camera['person_count'] = person_count
                    camera['chair_count'] = chair_count
                    camera['occupancy_rate'] = round(occupancy_rate * 100, 2)  # Porcentaje
                    camera['last_update'] = datetime.now()
                    camera['status'] = 'connected'
                    camera['last_frame'] = frame
                    
                    # Log de detección
                    if person_count > 0:
                        print(f"👥 {camera_name}: {person_count} personas, {chair_count} sillas ({camera['occupancy_rate']}% ocupación)")
                    
                else:
                    camera['status'] = 'no_frame'
                    
                time.sleep(1)  # Procesar aproximadamente 1 FPS
                
            except Exception as e:
                print(f"❌ Error en {camera_name}: {str(e)}")
                camera['status'] = f'error: {str(e)}'
                time.sleep(5)  # Esperar antes de reintentar
    
    def _count_objects(self, results, class_id):
        """Contar objetos de una clase específica"""
        count = 0
        for result in results:
            if result.boxes is not None and result.boxes.cls is not None:
                for i, cls in enumerate(result.boxes.cls):
                    if int(cls) == class_id:
                        # Verificar confianza
                        if result.boxes.conf[i] > 0.5:
                            count += 1
        return count
    
    def start_detection(self, camera_name):
        """Iniciar detección para una cámara específica"""
        if camera_name not in self.cameras:
            print(f"❌ Cámara {camera_name} no encontrada")
            return False
            
        # Verificar si ya hay un hilo activo para esta cámara
        for thread in self.detection_threads:
            if thread.name == f"detection_{camera_name}":
                print(f"ℹ️  Detección ya activa para {camera_name}")
                return True
        
        thread = threading.Thread(
            target=self.process_camera,
            args=(camera_name,),
            name=f"detection_{camera_name}"
        )
        thread.daemon = True
        thread.start()
        self.detection_threads.append(thread)
        
        print(f"✅ Detección iniciada para {camera_name}")
        return True
    
    def start_all(self):
        """Iniciar todas las cámaras"""
        self.running = True
        started_count = 0
        
        for camera_name in self.cameras.keys():
            if self.start_detection(camera_name):
                started_count += 1
                
        print(f"🚀 Iniciadas {started_count} de {len(self.cameras)} cámaras")
        return started_count
    
    def stop_detection(self, camera_name):
        """Detener detección para una cámara específica"""
        # El hilo se detendrá automáticamente cuando self.running = False
        if camera_name in self.cameras:
            self.cameras[camera_name]['status'] = 'stopped'
            print(f"⏹️  Detección detenida para {camera_name}")
    
    def stop_all(self):
        """Detener todas las cámaras"""
        self.running = False
        print("🛑 Todas las detecciones detenidas")
    
    def get_camera_data(self, camera_name):
        """Obtener datos de una cámara específica"""
        return self.cameras.get(camera_name)
    
    def get_all_cameras_data(self):
        """Obtener datos de todas las cámaras"""
        return {name: data for name, data in self.cameras.items()}
    
    def remove_camera(self, camera_name):
        """Remover una cámara del sistema"""
        if camera_name in self.cameras:
            self.stop_detection(camera_name)
            del self.cameras[camera_name]
            print(f"🗑️  Cámara {camera_name} removida")
            return True
        return False

# Instancia global del detector
detector = AttendanceDetector()