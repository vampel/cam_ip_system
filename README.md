# 🎯 Sistema de Asistencia Automatizado con Computer Vision

Sistema de control de asistencia automático usando **YOLO**, **OpenCV** y **Shinobi** para detección de ocupación en salones de clase mediante cámaras IP.

## 🚀 Características Principales
- **Detección en tiempo real** de personas y sillas usando YOLOv8
- **Dashboard React** moderno y responsive
- **Base de datos MySQL** para almacenamiento robusto
- **Soporte múltiples cámaras** via Shinobi CCTV
- **Cálculo automático** de porcentaje de ocupación
- **API REST** para integración con otros sistemas

## 🛠️ Stack Tecnológico

### 🤖 Computer Vision
- **YOLOv8** (Ultralytics) - Detección de objetos
- **OpenCV** - Procesamiento de imágenes
- **NumPy** - Cálculos numéricos

### 🌐 Backend
- **Django 4.2** - Framework web
- **Django REST Framework** - API
- **MySQL** - Base de datos principal
- **mysqlclient** - Conector MySQL para Django

### ⚛️ Frontend (React)
- **React 18** - Biblioteca de interfaz de usuario
- **TypeScript** - Tipado estático
- **Tailwind CSS** - Framework de estilos
- **Chart.js + React-Chartjs-2** - Gráficos en tiempo real
- **Axios** - Cliente HTTP

### 📷 Video Streaming
- **Shinobi CCTV** - Gestión de cámaras IP
- **ESP32-CAM** - Cámaras económicas
- **RTSP/HTTP** - Protocolos de streaming

## 📁 Estructura del Proyecto

cam_ip_system/  
├── backend/ # Django Backend 
│ ├── messaging/ # 
│ ├── attendance_system/ # Configuración Django  
│ ├── dashboard/ # host web temp 
│ ├── detection/ # Lógica de detección YOLO
│ │ ├── management/ # MQrabbit(?)
│ │ ├── yolo_detector.py  
│ │ ├── views.py  
│ │ └── urls.py  
│ ├── requirements.txt  
│ └── manage.py  
└── README.md  



## 📋 Instalación

### Requisitos Previos
- Python 3.8 o superior
- pip actualizado
- RabbitMQ instalado (ver sección de RabbitMQ)

### Paso 1: Clonar repositorio
```bash
git clone https://github.com/vampel/cam_ip_system.git
cd cam_ip_system/backend
```

### Paso 2: Crear entorno virtual
```bash
python -m venv venv
```

### Paso 3: Activar entorno virtual
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### Paso 4: Actualizar pip
```bash
python -m pip install --upgrade pip
```

### Paso 5: Instalar PyTorch (CPU)
```bash
# IMPORTANTE: Instalar PRIMERO PyTorch desde su índice oficial
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

> **Nota:** Si tienes GPU NVIDIA y quieres usar CUDA:
> ```bash
> pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
> ```

### Paso 6: Instalar resto de dependencias
```bash
pip install -r requirements.txt
```

### Paso 7: Verificar instalación
```bash
# Verificar PyTorch
python -c "import torch; print(f'PyTorch: {torch.__version__}')"

# Verificar YOLO
python -c "from ultralytics import YOLO; print('YOLO: OK')"

# Verificar OpenCV
python -c "import cv2; print(f'OpenCV: {cv2.__version__}')"
```

### Paso 8: Configurar Django
```bash
# Crear superusuario para login
python manage.py createsuperuser

# Iniciar servidor de desarrollo
python manage.py runserver
```

### Paso 9: Acceder al sistema
```
http://127.0.0.1:8000
```

---

## 🐰 Instalar RabbitMQ

RabbitMQ es un servidor independiente que debe instalarse en tu sistema operativo (NO en el venv).

### Windows:
1. **Descargar e instalar Erlang:** https://www.erlang.org/downloads
2. **Descargar e instalar RabbitMQ:** https://www.rabbitmq.com/download.html
3. **Habilitar management plugin:**
```cmd
   cd "C:\Program Files\RabbitMQ Server\rabbitmq_server-x.x.x\sbin"
   rabbitmq-plugins enable rabbitmq_management
```
4. **Iniciar servicio:**
```cmd
   net start RabbitMQ
```

### Linux (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install rabbitmq-server
sudo systemctl enable rabbitmq-server
sudo systemctl start rabbitmq-server
sudo rabbitmq-plugins enable rabbitmq_management
```

### macOS:
```bash
brew install rabbitmq
brew services start rabbitmq
rabbitmq-plugins enable rabbitmq_management
```

### Verificar RabbitMQ:
- **Interfaz web:** http://localhost:15672
- **Usuario:** `guest`
- **Contraseña:** `guest`

---

## 🚀 Ejecutar el Sistema Completo

### Terminal 1 - Django Server
```bash
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
python manage.py runserver
```

### Terminal 2 - RabbitMQ Consumer (Opcional)
```bash
venv\Scripts\activate
python manage.py run_rabbitmq_consumer --queue detection_results
```

### Terminal 3 - Navegador
```
http://127.0.0.1:8000
```

---

## 🔧 Solución de Problemas

### Error: "Could not find a version that satisfies the requirement torch"
**Solución:** Asegúrate de instalar PyTorch PRIMERO y desde su índice oficial:
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### Error: "No module named 'ultralytics'"
**Solución:** Instala las dependencias después de PyTorch:
```bash
pip install -r requirements.txt
```

### Error: RabbitMQ connection refused
**Solución:** Verifica que RabbitMQ esté corriendo:
```bash
# Windows
net start RabbitMQ

# Linux
sudo systemctl status rabbitmq-server
```

### Error: "ImportError: DLL load failed" (Windows)
**Solución:** Instala Visual C++ Redistributable:
https://aka.ms/vs/17/release/vc_redist.x64.exe