# detection/camera_manager.py
import threading
import time
import io
from datetime import datetime
import traceback

try:
    import cv2
except Exception:
    cv2 = None

import numpy as np
import random
import logging

logger = logging.getLogger(__name__)

# Optional: if ultralytics is installed, we'll try to use it
DETECTION_ENABLED = False
YOLO_MODEL = None
YOLO_MODEL_PATH = "yolov8n.pt"  # default; asegúrate que exista o se descargará por ultralytics

try:
    from ultralytics import YOLO
    try:
        YOLO_MODEL = YOLO(YOLO_MODEL_PATH)
        DETECTION_ENABLED = True
        logger.info("Ultralytics YOLO cargado correctamente.")
    except Exception as e:
        logger.warning(f"No se pudo cargar el modelo YOLO: {e}\nSe trabajará con detecciones mock.")
        DETECTION_ENABLED = False
except Exception:
    logger.info("ultralytics no está instalado; usando detecciones mock.")
    DETECTION_ENABLED = False


class Camera:
    def __init__(self, camera_id: str, source: str, detection_interval: float = 1.0):
        """
        source: ruta RTSP, HTTP, archivo local o Youtube/stream (si es compatible con VideoCapture)
        """
        self.camera_id = camera_id
        self.source = source
        self.detection_interval = detection_interval
        self._capture = None
        self._thread = None
        self._running = False
        self._lock = threading.RLock()
        self.last_frame = None          # JPEG bytes
        self.last_frame_ts = None
        self.last_detections = []       # list of detection dicts
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
        # wait for thread to finish
        if self._thread:
            self._thread.join(timeout=2.0)
        # release capture
        if self._capture:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None
        logger.info(f"Camera {self.camera_id} stopped.")
        return True

    def _open_capture(self):
        if cv2 is None:
            raise RuntimeError("cv2 no disponible. Instala opencv-python(-headless).")
        # Try to open capture; allow retries
        # If source is numeric string, try as index
        attempts = 0
        while attempts < 3:
            try:
                src = self.source
                # if source looks like an int index
                if isinstance(src, str) and src.isdigit():
                    src = int(src)
                cap = cv2.VideoCapture(src, cv2.CAP_ANY)
                # small wait for camera to warm
                time.sleep(0.3)
                if cap is not None and cap.isOpened():
                    return cap
                else:
                    try:
                        cap.release()
                    except Exception:
                        pass
            except Exception:
                logger.debug("error opening capture", exc_info=True)
            attempts += 1
            time.sleep(0.5)
        raise RuntimeError(f"No se pudo abrir VideoCapture para {self.source}")

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
                    # no frame, try reopen once
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
                # update fps roughly
                elapsed = time.time() - read_start
                if elapsed > 0:
                    self.fps = frame_count / elapsed

                # encode to JPEG and save
                try:
                    _, buf = cv2.imencode('.jpg', frame)
                    jpeg_bytes = buf.tobytes()
                    with self._lock:
                        self.last_frame = jpeg_bytes
                        self.last_frame_ts = datetime.utcnow().isoformat() + "Z"
                except Exception as e:
                    logger.exception(f"[{self.camera_id}] Error al codificar frame JPEG: {e}")

                # detection (run only every detection_interval)
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

                # small sleep to avoid tight loop
                # aim to keep loop responsive but not 100% CPU
                time.sleep(0.01)

            except Exception as e:
                logger.exception(f"[{self.camera_id}] Error en loop de captura: {e}")
                self.last_error = str(e)
                time.sleep(1.0)

        # cleanup when leaving loop
        try:
            if self._capture:
                self._capture.release()
        except Exception:
            pass

    def _run_detection(self, frame):
        """
        Ejecuta detección sobre el frame (BGR numpy array).
        Devuelve lista de detections en formato:
        [{'id': str, 'label': str, 'confidence': float, 'bbox': [x1,y1,x2,y2]}...]
        """
        detections = []

        if DETECTION_ENABLED and YOLO_MODEL is not None:
            try:
                # ultralytics expects RGB
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = YOLO_MODEL(rgb)  # quick inference; model handles batching
                # results may contain multiple frames; we take first
                for r in results:
                    boxes = r.boxes
                    if boxes is None:
                        continue
                    for b in boxes:
                        # depending on ultralytics version, b may have .xyxy, .conf, .cls
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
                        })
                return detections
            except Exception:
                # fallback to mock below
                logger.exception(f"[{self.camera_id}] fallo en ultralytics detection, uso mock")
        # Mock detections if no model
        h, w = frame.shape[:2] if hasattr(frame, 'shape') else (360, 640)
        for i in range(random.randint(0, 3)):
            x1 = random.randint(0, max(0, w - 100))
            y1 = random.randint(0, max(0, h - 100))
            x2 = x1 + random.randint(40, 160)
            y2 = y1 + random.randint(60, 240)
            detections.append({
                'id': f"{self.camera_id}_{int(time.time()*1000)}_{i}",
                'label': random.choice(['person', 'car', 'bicycle']),
                'confidence': round(0.5 + random.random() * 0.5, 3),
                'bbox': [x1, y1, min(x2, w-1), min(y2, h-1)]
            })
        return detections


class CameraManager:
    def __init__(self):
        self.cameras = {}  # camera_id -> Camera
        self._lock = threading.RLock()

    def add_camera(self, camera_id: str, source: str) -> bool:
        with self._lock:
            if camera_id in self.cameras:
                logger.warning(f"add_camera: {camera_id} ya existe")
                return False
            cam = Camera(camera_id, source)
            self.cameras[camera_id] = cam
            logger.info(f"Cámara añadida: {camera_id} -> {source}")
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
            }

    def get_camera_frame(self, camera_id: str):
        cam = self.cameras.get(camera_id)
        if not cam:
            return None
        with cam._lock:
            return cam.last_frame

    def get_camera_detections(self, camera_id: str):
        cam = self.cameras.get(camera_id)
        if not cam:
            return []
        with cam._lock:
            return list(cam.last_detections)

    def get_cameras_info(self):
        with self._lock:
            out = []
            for cid, cam in self.cameras.items():
                out.append(self.get_camera_status(cid))
            return out


# single global instance
camera_manager = CameraManager()

# optional: preload a demo camera if none exists (commented)
# camera_manager.add_camera("demo", 0)
# camera_manager.start_camera("demo")
