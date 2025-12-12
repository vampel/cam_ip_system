# detection/camera_manager.py - VERSIÓN DEFINITIVA
import threading
import time
from datetime import datetime
import traceback

try:
    import cv2
except Exception:
    cv2 = None

import numpy as np
import logging

logger = logging.getLogger(__name__)

# YOLO detection
DETECTION_ENABLED = False
YOLO_MODEL = None
YOLO_MODEL_PATH = "yolov8n.pt"

try:
    from ultralytics import YOLO
    try:
        YOLO_MODEL = YOLO(YOLO_MODEL_PATH)
        DETECTION_ENABLED = True
        print("[OK] Ultralytics YOLO cargado correctamente - DETECCION REAL HABILITADA")
    except Exception as e:
        print(f"[ERROR] No se pudo cargar YOLO: {e}")
        DETECTION_ENABLED = False
except Exception:
    print("[ERROR] ultralytics no está instalado - pip install ultralytics")
    DETECTION_ENABLED = False


class Camera:
    def __init__(self, camera_id: str, source: str, detection_interval: float = 1.0):
        self.camera_id = camera_id
        self.source = source
        self.original_source = source
        self.detection_interval = detection_interval
        self._capture = None
        self._thread = None
        self._running = False
        self._lock = threading.RLock()
        self.last_frame = None
        self.last_frame_ts = None
        self.last_detections = []
        self.last_error = None
        self.fps = 0.0
        self._last_detection_time = 0.0
        self.status = 'stopped'

    def start(self):
        with self._lock:
            if self._running:
                print(f"[{self.camera_id}] Ya está corriendo")
                return True
            self._running = True
            self.status = 'starting'
            self._thread = threading.Thread(
                target=self._loop_safe, 
                name=f"CameraThread-{self.camera_id}", 
                daemon=True
            )
            self._thread.start()
            print(f"[{self.camera_id}] Thread iniciado")
            return True

    def stop(self):
        with self._lock:
            if not self._running:
                return True
            self._running = False
            self.status = 'stopped'
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        
        if self._capture:
            try:
                self._capture.release()
            except:
                pass
            self._capture = None
        
        print(f"[{self.camera_id}] Detenido")
        return True

    def _convert_youtube_url(self, url: str) -> str:
        """Convierte URL de YouTube a stream directo"""
        if 'youtube.com' not in url and 'youtu.be' not in url:
            return url
        
        try:
            import yt_dlp
            
            print(f"[{self.camera_id}] Extrayendo YouTube...")
            
            configs = [
                {'name': 'Android', 'opts': {'format': 'best[height<=480]', 'quiet': True, 'no_warnings': True, 'extractor_args': {'youtube': {'player_client': ['android']}}}},
                {'name': 'iOS', 'opts': {'format': 'best[height<=480]', 'quiet': True, 'no_warnings': True, 'extractor_args': {'youtube': {'player_client': ['ios']}}}},
                {'name': 'Default', 'opts': {'format': 'best[height<=480]', 'quiet': True, 'no_warnings': True}}
            ]
            
            for config in configs:
                try:
                    with yt_dlp.YoutubeDL(config['opts']) as ydl:
                        info = ydl.extract_info(url, download=False)
                        stream_url = info.get('url')
                        if stream_url:
                            print(f"[{self.camera_id}] ✅ YouTube OK con {config['name']}")
                            return stream_url
                except:
                    continue
            
            raise RuntimeError("No se pudo extraer YouTube")
        except ImportError:
            raise RuntimeError("yt-dlp no instalado - pip install yt-dlp")
        except Exception as e:
            raise RuntimeError(f"YouTube error: {e}")

    def _open_capture(self):
        """Abre VideoCapture"""
        if cv2 is None:
            raise RuntimeError("OpenCV no disponible")
        
        try:
            src = self._convert_youtube_url(self.source)
        except Exception as e:
            print(f"[{self.camera_id}] Error conversión: {e}")
            raise
        
        for attempt in range(3):
            try:
                if isinstance(src, str) and src.isdigit():
                    src = int(src)
                
                cap = cv2.VideoCapture(src, cv2.CAP_ANY)
                time.sleep(0.5)
                
                if cap is not None and cap.isOpened():
                    print(f"[{self.camera_id}] ✅ VideoCapture OK")
                    return cap
                else:
                    try:
                        cap.release()
                    except:
                        pass
            except Exception as e:
                print(f"[{self.camera_id}] Intento {attempt+1}/3: {e}")
            
            if attempt < 2:
                time.sleep(1.0)
        
        raise RuntimeError("No se pudo abrir VideoCapture después de 3 intentos")

    def _loop_safe(self):
        """Loop principal PROTEGIDO - NO mata el servidor si falla"""
        try:
            self._loop()
        except Exception as e:
            error_msg = str(e)
            print(f"[{self.camera_id}] ❌ ERROR: {error_msg}")
            
            with self._lock:
                self.status = 'error'
                self.last_error = error_msg
                self._running = False
            
            print(f"[{self.camera_id}] Thread terminado (servidor OK)")

    def _loop(self):
        """Loop principal"""
        try:
            self._capture = self._open_capture()
            with self._lock:
                self.status = 'running'
        except Exception as e:
            with self._lock:
                self.last_error = str(e)
                self.status = 'error'
            raise

        read_start = time.time()
        frame_count = 0

        while self._running:
            try:
                ret, frame = self._capture.read()
                
                if not ret or frame is None:
                    print(f"[{self.camera_id}] Sin frame - reconectando...")
                    try:
                        self._capture.release()
                    except:
                        pass
                    time.sleep(0.5)
                    try:
                        self._capture = self._open_capture()
                        continue
                    except Exception as e:
                        with self._lock:
                            self.last_error = str(e)
                            self.status = 'error'
                        time.sleep(2.0)
                        continue

                frame_count += 1
                elapsed = time.time() - read_start
                if elapsed > 0:
                    self.fps = frame_count / elapsed

                # Encode JPEG
                try:
                    _, buf = cv2.imencode('.jpg', frame)
                    jpeg_bytes = buf.tobytes()
                    with self._lock:
                        self.last_frame = jpeg_bytes
                        self.last_frame_ts = datetime.utcnow().isoformat() + "Z"
                        if self.status != 'running':
                            self.status = 'running'
                except Exception as e:
                    print(f"[{self.camera_id}] Error JPEG: {e}")

                # Detección YOLO
                now = time.time()
                if (now - self._last_detection_time) >= self.detection_interval:
                    self._last_detection_time = now
                    try:
                        detections = self._run_detection(frame)
                        with self._lock:
                            self.last_detections = detections
                    except Exception as e:
                        with self._lock:
                            self.last_detections = []

                time.sleep(0.01)

            except Exception as e:
                print(f"[{self.camera_id}] Error loop: {e}")
                with self._lock:
                    self.last_error = str(e)
                    self.status = 'error'
                time.sleep(1.0)

        try:
            if self._capture:
                self._capture.release()
        except:
            pass
        
        with self._lock:
            self.status = 'stopped'

    def _run_detection(self, frame):
        """Detección YOLO con logs detallados"""
        if not DETECTION_ENABLED or YOLO_MODEL is None:
            return []

        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = YOLO_MODEL(rgb, verbose=False)
            
            detections = []
            for r in results:
                boxes = r.boxes
                if boxes is None:
                    continue
                    
                for b in boxes:
                    try:
                        xyxy = b.xyxy[0].tolist() if hasattr(b, 'xyxy') else list(b.xyxy)
                    except:
                        xyxy = [0, 0, 0, 0]
                    
                    conf = float(b.conf[0] if hasattr(b, 'conf') else b.conf)
                    cls = int(b.cls[0] if hasattr(b, 'cls') else b.cls)
                    label = YOLO_MODEL.names.get(cls, str(cls)) if hasattr(YOLO_MODEL, 'names') else str(cls)
                    
                    detections.append({
                        'id': f"{self.camera_id}_{int(time.time()*1000)}_{len(detections)}",
                        'label': label,
                        'confidence': round(conf, 4),
                        'bbox': [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])],
                        'timestamp': datetime.utcnow().isoformat() + "Z"
                    })
            
            # LOGS DETALLADOS para VSCode
            person_count = sum(1 for d in detections if d.get('label') == 'person')
            other_count = len(detections) - person_count
            
            # Contar por categoría
            categories = {}
            for d in detections:
                label = d.get('label', 'unknown')
                categories[label] = categories.get(label, 0) + 1
            
            if detections:
                categories_str = ', '.join([f"{k}: {v}" for k, v in categories.items()])
                print(f"[{self.camera_id}] 👁️  DETECTADO: {person_count} personas, {other_count} otros ({categories_str})")
            
            return detections
            
        except Exception as e:
            print(f"[{self.camera_id}] Error YOLO: {e}")
            return []


class CameraManager:
    def __init__(self):
        self.cameras = {}
        self._lock = threading.RLock()
        
        if not DETECTION_ENABLED:
            print("⚠️  YOLO NO DISPONIBLE - pip install ultralytics")

    def add_camera(self, camera_id: str, source: str) -> bool:
        with self._lock:
            if camera_id in self.cameras:
                print(f"[{camera_id}] Ya existe")
                return False
            cam = Camera(camera_id, source)
            self.cameras[camera_id] = cam
            print(f"[{camera_id}] ➕ Añadida: {source}")
            return True

    def start_camera(self, camera_id: str) -> bool:
        with self._lock:
            cam = self.cameras.get(camera_id)
            if not cam:
                print(f"[{camera_id}] No encontrada")
                return False
            return cam.start()

    def stop_camera(self, camera_id: str) -> bool:
        with self._lock:
            cam = self.cameras.get(camera_id)
            if not cam:
                return False
            return cam.stop()

    def remove_camera(self, camera_id: str) -> bool:
        with self._lock:
            cam = self.cameras.pop(camera_id, None)
        if cam:
            try:
                cam.stop()
            except:
                pass
            print(f"[{camera_id}] 🗑️  Eliminada")
            return True
        return False

    def get_camera_status(self, camera_id: str):
        cam = self.cameras.get(camera_id)
        if not cam:
            return None
        with cam._lock:
            return {
                'camera_id': cam.camera_id,
                'source': cam.source,
                'running': cam._running,
                'status': cam.status,
                'last_frame_ts': cam.last_frame_ts,
                'last_error': cam.last_error,
                'fps': round(cam.fps, 2),
                'detections_count': len(cam.last_detections),
                'yolo_enabled': DETECTION_ENABLED
            }

    def get_camera_frame(self, camera_id: str, with_boxes: bool = False):
        """Obtiene frame con o sin bounding boxes"""
        cam = self.cameras.get(camera_id)
        if not cam:
            return None
        
        with cam._lock:
            if not with_boxes or not cam.last_detections:
                return cam.last_frame
            
            if cam.last_frame:
                try:
                    # Decodificar JPEG
                    nparr = np.frombuffer(cam.last_frame, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    # Dibujar bounding boxes
                    for det in cam.last_detections:
                        bbox = det.get('bbox', [])
                        if len(bbox) == 4:
                            x1, y1, x2, y2 = bbox
                            label = det.get('label', 'unknown')
                            conf = det.get('confidence', 0.0)
                            
                            # Verde para personas, naranja para otros
                            color = (0, 255, 0) if label == 'person' else (0, 165, 255)
                            
                            # Rectángulo
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            
                            # Etiqueta
                            text = f"{label} {conf:.2f}"
                            (text_width, text_height), baseline = cv2.getTextSize(
                                text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2
                            )
                            cv2.rectangle(frame, (x1, y1 - text_height - 5), 
                                        (x1 + text_width, y1), color, -1)
                            cv2.putText(frame, text, (x1, y1 - 5), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                    
                    # Recodificar
                    _, buf = cv2.imencode('.jpg', frame)
                    return buf.tobytes()
                    
                except Exception as e:
                    print(f"[{camera_id}] Error dibujando boxes: {e}")
            
            return cam.last_frame

    def get_camera_detections(self, camera_id: str, limit: int = 20):
        cam = self.cameras.get(camera_id)
        if not cam:
            return []
        with cam._lock:
            detections = list(cam.last_detections)
            return detections[:limit] if limit else detections

    def get_detection_statistics(self, camera_id: str):
        cam = self.cameras.get(camera_id)
        if not cam:
            return {}
        
        with cam._lock:
            detections = cam.last_detections
            
            if not detections:
                return {
                    'total_detections': 0,
                    'avg_confidence': 0.0,
                    'yolo_enabled': DETECTION_ENABLED
                }
            
            total = len(detections)
            avg_conf = sum(d.get('confidence', 0) for d in detections) / total if total > 0 else 0
            
            return {
                'total_detections': total,
                'avg_confidence': round(avg_conf, 3),
                'yolo_enabled': DETECTION_ENABLED,
                'labels': list(set(d.get('label', 'unknown') for d in detections))
            }

    def get_cameras_info(self):
        with self._lock:
            out = []
            for cid, cam in self.cameras.items():
                status = self.get_camera_status(cid)
                if status:
                    person_count = sum(1 for d in cam.last_detections if d.get('label') == 'person')
                    status['person_count'] = person_count
                    out.append(status)
            return out


# Instancia global
camera_manager = CameraManager()