# detection/camera_manager.py - VERSIÓN COMPLETA CON YOUTUBE
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

# YOLO detection - REAL, NO MOCK
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
        print(f"[ERROR] No se pudo cargar el modelo YOLO: {e}")
        print("[WARNING] INSTALA YOLO PARA USAR DETECCIÓN REAL")
        DETECTION_ENABLED = False
except Exception:
    print("[ERROR] ultralytics no está instalado")
    print("[WARNING] Instala con: pip install ultralytics")
    DETECTION_ENABLED = False


class Camera:
    def __init__(self, camera_id: str, source: str, detection_interval: float = 1.0):
        """
        source: ruta RTSP, HTTP, archivo local, YouTube URL, o stream compatible con VideoCapture
        """
        self.camera_id = camera_id
        self.source = source
        self.original_source = source  # Guardar URL original
        self.detection_interval = detection_interval
        self._capture = None
        self._thread = None
        self._running = False
        self._lock = threading.RLock()
        self.last_frame = None          # JPEG bytes
        self.last_frame_ts = None
        self.last_detections = []       # SOLO detecciones REALES de YOLO
        self.last_error = None
        self.fps = 0.0
        self._last_detection_time = 0.0

    def start(self):
        with self._lock:
            if self._running:
                return True
            self._running = True
            self._thread = threading.Thread(target=self._loop, name=f"CameraThread-{self.camera_id}", daemon=True)
            self._thread.start()
            logger.info(f"Camera {self.camera_id} thread started.")
            return True

    def stop(self):
        with self._lock:
            if not self._running:
                return True
            self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._capture:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None
        logger.info(f"Camera {self.camera_id} stopped.")
        return True

    def _convert_youtube_url(self, url: str) -> str:
        """
        Convierte URL de YouTube a stream directo usando yt-dlp
        Soporta múltiples estrategias de cliente para mayor compatibilidad
        """
        if 'youtube.com' not in url and 'youtu.be' not in url:
            return url
        
        try:
            import yt_dlp
            
            print(f"[{self.camera_id}] [YOUTUBE] Extrayendo stream de: {url}")
            
            # Múltiples estrategias de cliente
            configs = [
                {
                    'name': 'Android client',
                    'opts': {
                        'format': 'best[height<=480]',
                        'quiet': True,
                        'no_warnings': True,
                        'extractor_args': {'youtube': {'player_client': ['android']}},
                    }
                },
                {
                    'name': 'iOS client', 
                    'opts': {
                        'format': 'best[height<=480]',
                        'quiet': True,
                        'no_warnings': True,
                        'extractor_args': {'youtube': {'player_client': ['ios']}},
                    }
                },
                {
                    'name': 'Web client',
                    'opts': {
                        'format': 'best[height<=480]',
                        'quiet': True,
                        'no_warnings': True,
                        'extractor_args': {'youtube': {'player_client': ['web']}},
                    }
                },
                {
                    'name': 'Default',
                    'opts': {
                        'format': 'best[height<=480]',
                        'quiet': True,
                        'no_warnings': True,
                    }
                }
            ]
            
            for config in configs:
                try:
                    print(f"[{self.camera_id}] [YOUTUBE] Intentando con {config['name']}...")
                    with yt_dlp.YoutubeDL(config['opts']) as ydl:
                        info = ydl.extract_info(url, download=False)
                        stream_url = info.get('url')
                        if stream_url:
                            print(f"[{self.camera_id}] [YOUTUBE] ✅ Stream obtenido con {config['name']}")
                            return stream_url
                except Exception as e:
                    print(f"[{self.camera_id}] [YOUTUBE] ❌ Falló {config['name']}: {e}")
                    continue
            
            print(f"[{self.camera_id}] [YOUTUBE] ❌ Todas las estrategias fallaron")
            raise RuntimeError("No se pudo extraer stream de YouTube con ninguna estrategia")
            
        except ImportError:
            print(f"[{self.camera_id}] [ERROR] yt-dlp no está instalado")
            print(f"[{self.camera_id}] [ERROR] Instala con: pip install yt-dlp")
            raise RuntimeError("yt-dlp no está instalado")
        except Exception as e:
            print(f"[{self.camera_id}] [YOUTUBE] Error: {e}")
            raise

    def _open_capture(self):
        if cv2 is None:
            raise RuntimeError("cv2 no disponible. Instala opencv-python(-headless).")
        
        # Convertir URL de YouTube si es necesario
        try:
            src = self._convert_youtube_url(self.source)
        except Exception as e:
            print(f"[{self.camera_id}] [ERROR] No se pudo convertir URL: {e}")
            raise
        
        attempts = 0
        while attempts < 3:
            try:
                # Si es un número, convertir a int
                if isinstance(src, str) and src.isdigit():
                    src = int(src)
                
                print(f"[{self.camera_id}] [CAMERA] Abriendo VideoCapture...")
                cap = cv2.VideoCapture(src, cv2.CAP_ANY)
                time.sleep(0.5)
                
                if cap is not None and cap.isOpened():
                    print(f"[{self.camera_id}] [CAMERA] ✅ VideoCapture abierto correctamente")
                    return cap
                else:
                    print(f"[{self.camera_id}] [CAMERA] ❌ VideoCapture no se pudo abrir")
                    try:
                        cap.release()
                    except Exception:
                        pass
            except Exception as e:
                print(f"[{self.camera_id}] [CAMERA] ❌ Error: {e}")
                logger.debug("error opening capture", exc_info=True)
            
            attempts += 1
            if attempts < 3:
                print(f"[{self.camera_id}] [CAMERA] Reintentando... ({attempts}/3)")
                time.sleep(1.0)
        
        raise RuntimeError(f"No se pudo abrir VideoCapture después de 3 intentos")

    def _loop(self):
        try:
            self._capture = self._open_capture()
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"[{self.camera_id}] Error al abrir la fuente: {e}")
            self._running = False
            return

        read_start = time.time()
        frame_count = 0

        while self._running:
            try:
                t0 = time.time()
                ret, frame = self._capture.read()
                if not ret or frame is None:
                    logger.warning(f"[{self.camera_id}] No frame recibido. Intentando reconectar...")
                    try:
                        self._capture.release()
                    except Exception:
                        pass
                    time.sleep(0.5)
                    try:
                        self._capture = self._open_capture()
                        continue
                    except Exception as e:
                        self.last_error = str(e)
                        logger.error(f"[{self.camera_id}] Reconexión fallida: {e}")
                        time.sleep(1.0)
                        continue

                frame_count += 1
                elapsed = time.time() - read_start
                if elapsed > 0:
                    self.fps = frame_count / elapsed

                # Encode to JPEG
                try:
                    _, buf = cv2.imencode('.jpg', frame)
                    jpeg_bytes = buf.tobytes()
                    with self._lock:
                        self.last_frame = jpeg_bytes
                        self.last_frame_ts = datetime.utcnow().isoformat() + "Z"
                except Exception as e:
                    logger.exception(f"[{self.camera_id}] Error al codificar frame JPEG: {e}")

                # DETECCIÓN REAL (solo cada detection_interval)
                now = time.time()
                if (now - self._last_detection_time) >= self.detection_interval:
                    self._last_detection_time = now
                    try:
                        detections = self._run_detection(frame)
                        with self._lock:
                            self.last_detections = detections
                    except Exception as e:
                        logger.exception(f"[{self.camera_id}] Error en detección: {e}")
                        with self._lock:
                            self.last_detections = []

                time.sleep(0.01)

            except Exception as e:
                logger.exception(f"[{self.camera_id}] Error en loop de captura: {e}")
                self.last_error = str(e)
                time.sleep(1.0)

        try:
            if self._capture:
                self._capture.release()
        except Exception:
            pass

    def _run_detection(self, frame):
        """
        ⚠️ SOLO DETECCIONES REALES - NO MOCK
        Si YOLO no está disponible, retorna lista vacía
        """
        detections = []

        if not DETECTION_ENABLED or YOLO_MODEL is None:
            return []

        # DETECCIÓN REAL CON YOLO
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = YOLO_MODEL(rgb, verbose=False)
            
            for r in results:
                boxes = r.boxes
                if boxes is None:
                    continue
                for b in boxes:
                    try:
                        xyxy = b.xyxy[0].tolist() if hasattr(b, 'xyxy') else b.xyxy.tolist()
                    except Exception:
                        try:
                            xyxy = list(map(float, b.xyxy))
                        except Exception:
                            xyxy = [0, 0, 0, 0]
                    
                    conf = float(b.conf[0]) if hasattr(b, 'conf') else float(b.conf)
                    cls = int(b.cls[0]) if hasattr(b, 'cls') else int(b.cls)
                    label = YOLO_MODEL.names.get(cls, str(cls)) if hasattr(YOLO_MODEL, 'names') else str(cls)
                    
                    detections.append({
                        'id': f"{self.camera_id}_{int(time.time()*1000)}_{len(detections)}",
                        'label': label,
                        'confidence': round(conf, 4),
                        'bbox': [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])],
                        'timestamp': datetime.utcnow().isoformat() + "Z"
                    })
            
            # LOGS MEJORADOS - Mostrar desglose
            person_count = sum(1 for d in detections if d.get('label') == 'person')
            other_count = len(detections) - person_count
            
            if detections:
                print(f"[{self.camera_id}] [OK] Deteccion REAL: {len(detections)} objetos ({person_count} personas, {other_count} otros)")
            
            return detections
            
        except Exception as e:
            logger.exception(f"[{self.camera_id}] [ERROR] Error en YOLO detection: {e}")
            return []


class CameraManager:
    def __init__(self):
        self.cameras = {}
        self._lock = threading.RLock()
        
        if not DETECTION_ENABLED:
            logger.warning("="*60)
            logger.warning("[WARNING] YOLO NO DISPONIBLE - DETECCIÓN DESHABILITADA")
            logger.warning("[WARNING] Instala con: pip install ultralytics")
            logger.warning("[WARNING] Las cámaras capturarán video pero SIN detección")
            logger.warning("="*60)

    def add_camera(self, camera_id: str, source: str) -> bool:
        with self._lock:
            if camera_id in self.cameras:
                logger.warning(f"add_camera: {camera_id} ya existe")
                return False
            cam = Camera(camera_id, source)
            self.cameras[camera_id] = cam
            logger.info(f"[CAMERA] Cámara añadida: {camera_id} -> {source}")
            return True

    def start_camera(self, camera_id: str) -> bool:
        with self._lock:
            cam = self.cameras.get(camera_id)
            if not cam:
                logger.warning(f"start_camera: {camera_id} no encontrada")
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
            except Exception:
                pass
            logger.info(f"Cámara {camera_id} eliminada")
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
                'last_frame_ts': cam.last_frame_ts,
                'last_error': cam.last_error,
                'fps': round(cam.fps, 2),
                'detections_count': len(cam.last_detections),
                'yolo_enabled': DETECTION_ENABLED
            }

    def get_camera_frame(self, camera_id: str, with_boxes: bool = False):
        """
        Obtiene el frame de la cámara
        Si with_boxes=True, dibuja los bounding boxes de las detecciones REALES
        """
        cam = self.cameras.get(camera_id)
        if not cam:
            return None
        
        with cam._lock:
            if not with_boxes:
                return cam.last_frame
            
            # Dibujar bounding boxes SOLO si hay detecciones REALES
            if cam.last_frame and cam.last_detections:
                try:
                    # Decodificar JPEG
                    nparr = np.frombuffer(cam.last_frame, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    # Dibujar cada detección REAL
                    for det in cam.last_detections:
                        bbox = det.get('bbox', [])
                        if len(bbox) == 4:
                            x1, y1, x2, y2 = bbox
                            label = det.get('label', 'unknown')
                            conf = det.get('confidence', 0.0)
                            
                            # Color según el tipo
                            color = (0, 255, 0) if label == 'person' else (255, 165, 0)
                            
                            # Dibujar rectángulo
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            
                            # Dibujar etiqueta
                            text = f"{label} {conf:.2f}"
                            cv2.putText(frame, text, (x1, y1-10), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    
                    # Recodificar a JPEG
                    _, buf = cv2.imencode('.jpg', frame)
                    return buf.tobytes()
                    
                except Exception as e:
                    logger.error(f"Error dibujando boxes: {e}")
            
            return cam.last_frame

    def get_camera_detections(self, camera_id: str, limit: int = 20):
        """Retorna SOLO detecciones REALES"""
        cam = self.cameras.get(camera_id)
        if not cam:
            return []
        with cam._lock:
            detections = list(cam.last_detections)
            return detections[:limit] if limit else detections

    def get_detection_statistics(self, camera_id: str):
        """Estadísticas de detecciones REALES"""
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
                    # Agregar contador de personas (solo objetos de clase 'person')
                    person_count = sum(1 for d in cam.last_detections if d.get('label') == 'person')
                    status['person_count'] = person_count
                    out.append(status)
            return out


# Instancia global
camera_manager = CameraManager()