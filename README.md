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
```
├── backend/ # Django Backend
│ ├── attendance_system/ # Configuración Django
│ ├── detection/ # Lógica de detección YOLO
│ │ ├── yolo_detector.py
│ │ ├── views.py
│ │ └── urls.py
│ ├── requirements.txt
│ └── manage.py
├── frontend/ # React Frontend
│ ├── src/
│ │ ├── components/ # Componentes React
│ │ ├── pages/ # Páginas principales
│ │ ├── hooks/ # Custom hooks
│ │ ├── services/ # API services
│ │ └── styles/ # Estilos Tailwind
│ ├── package.json
│ └── tailwind.config.js
└── README.md
```

## ⚡ Instalación Rápida

### Prerrequisitos
- Python 3.8+
- Node.js 18+
- MySQL 8.0+
- Git

### 1. Clonar Repositorio
```bash
git clone https://github.com/vampel/cam_ip_system.git
cd cam_ip_system
