# detection/camera_manager.py - VERSIÓN CORRECTA
import cv2
import threading
import time
from datetime import datetime
from ultralytics import YOLO
import numpy as np

class CameraManager:
    def __init__(self):
        self.cameras = {}
        self.model = YOLO('yolov8n.pt')
        self.lock = threading.Lock()
        self.producer = None  # Inicializar después
    
    def _init_rabbitmq(self):
        """Inicializar RabbitMQ (lazy loading)"""
        if self.producer is None:
            try:
                from messaging.producer import RabbitMQProducer
                self.producer = RabbitMQProducer()
                print("✅ RabbitMQ Producer inicializado")
            except Exception as e:
                print(f"⚠️ RabbitMQ no disponible: {e}")
    
    def add_camera(self, camera_id, stream_url):
        with self.lock:
            self.cameras[camera_id] = {
                'stream_url': stream_url,
                'status': 'stopped',
                'thread': None,
                'last_detection': None,
                'person_count': 0,
                'last_update': None,
                'last_frame': None  # ✅ Agregar para video_feed
            }
    
    def remove_camera(self, camera_id):
        with self.lock:
            if camera_id in self.cameras:
                self.stop_camera(camera_id)
                del self.cameras[camera_id]
    
    def start_camera(self, camera_id):
        with self.lock:
            if camera_id in self.cameras and self.cameras[camera_id]['status'] == 'stopped':
                self._init_rabbitmq()  # ✅ Inicializar RabbitMQ si es necesario
                
                self.cameras[camera_id]['status'] = 'starting'
                thread = threading.Thread(target=self._process_stream, args=(camera_id,))
                self.cameras[camera_id]['thread'] = thread
                thread.daemon = True  # ✅ Importante para que se cierre con el programa
                thread.start()
                
                # 📤 Publicar evento a RabbitMQ
                if self.producer:
                    try:
                        self.producer.publish_camera_started(
                            camera_id,
                            self.cameras[camera_id]['stream_url']
                        )
                    except Exception as e:
                        print(f"⚠️ Error publicando a RabbitMQ: {e}")
    
    def stop_camera(self, camera_id):
        with self.lock:
            if camera_id in self.cameras:
                self.cameras[camera_id]['status'] = 'stopped'
                thread = self.cameras[camera_id].get('thread')
        
        # Esperar a que el thread termine (fuera del lock para evitar deadlock)
        if thread and thread.is_alive():
            thread.join(timeout=5)
    
    def _process_stream(self, camera_id):
        camera = self.cameras.get(camera_id)
        if not camera:
            return
            
        stream_url = camera['stream_url']
        
        # Intentar conectar a la cámara
        cap = cv2.VideoCapture(stream_url)
        
        if not cap.isOpened():
            with self.lock:
                if camera_id in self.cameras:
                    self.cameras[camera_id]['status'] = 'error'
            return
        
        with self.lock:
            if camera_id in self.cameras:
                self.cameras[camera_id]['status'] = 'running'
        
        while True:
            # Verificar si debemos detenernos
            with self.lock:
                if camera_id not in self.cameras or self.cameras[camera_id]['status'] != 'running':
                    break
            
            ret, frame = cap.read()
            
            if not ret:
                time.sleep(1)
                continue
            
            try:
                # Detección con YOLO
                results = self.model(frame, verbose=False)
                
                # Contar personas (clase 0 en COCO)
                person_count = 0
                for result in results:
                    boxes = result.boxes
                    if boxes is not None:
                        for box in boxes:
                            cls = int(box.cls[0])
                            if cls == 0:  # Person class
                                person_count += 1
                
                # Actualizar estado
                with self.lock:
                    if camera_id in self.cameras:
                        self.cameras[camera_id]['person_count'] = person_count
                        self.cameras[camera_id]['last_update'] = datetime.now().isoformat()
                        self.cameras[camera_id]['last_detection'] = datetime.now().isoformat()
                        self.cameras[camera_id]['last_frame'] = frame  # ✅ Guardar frame para streaming
                
                # 📤 Publicar resultado a RabbitMQ
                if self.producer:
                    try:
                        occupancy_rate = (person_count / 20) * 100  # Ejemplo: 20 sillas max
                        self.producer.publish_detection_result(
                            camera_id,
                            person_count,
                            20,  # chairs (ajustar según tu lógica)
                            occupancy_rate
                        )
                        
                        # 📤 Publicar alerta si ocupación alta
                        self.producer.publish_occupancy_alert(
                            camera_id,
                            occupancy_rate,
                            threshold=80
                        )
                    except Exception as e:
                        print(f"⚠️ Error publicando a RabbitMQ: {e}")
                
            except Exception as e:
                print(f"❌ Error procesando frame: {e}")
            
            time.sleep(0.1)  # Controlar FPS (~10 FPS)
        
        cap.release()
        with self.lock:
            if camera_id in self.cameras:
                self.cameras[camera_id]['status'] = 'stopped'
    
    def get_cameras_info(self):
        with self.lock:
            cameras_info = []
            for camera_id, camera_data in self.cameras.items():
                cameras_info.append({
                    'id': camera_id,
                    'name': camera_id,
                    'stream_url': camera_data['stream_url'],
                    'status': camera_data['status'],
                    'person_count': camera_data['person_count'],
                    'last_update': camera_data['last_update']
                })
            return cameras_info
    
    def get_camera_status(self, camera_id):
        with self.lock:
            if camera_id in self.cameras:
                return self.cameras[camera_id].copy()  # ✅ Devolver copia para evitar race conditions
            return None
    
    def start_all_cameras(self):
        camera_ids = list(self.cameras.keys())  # ✅ Copiar lista para evitar modificación durante iteración
        for camera_id in camera_ids:
            self.start_camera(camera_id)
    
    def stop_all_cameras(self):
        camera_ids = list(self.cameras.keys())
        for camera_id in camera_ids:
            self.stop_camera(camera_id)