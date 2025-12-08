# attendance_system/urls.py - URLS PRINCIPAL CORREGIDO
from django.contrib import admin
from django.urls import path, include
from detection import views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Redirección raíz al dashboard
    path('', views.dashboard, name='home'),
    
    # Auth
    path('web/login/', views.login_page, name='login_page'),
    path('web/login/submit/', views.login_submit, name='login_submit'),
    path('web/logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('web/dashboard/', views.dashboard, name='dashboard'),
    
    # Web Controls - NOMBRES CORREGIDOS
    path('web/cameras/add/', views.add_camera_view, name='add_camera'),
    path('web/cameras/<str:camera_sanitized_name>/control/', views.control_camera_view, name='control_camera'),
    path('web/cameras/<str:camera_sanitized_name>/delete/', views.remove_camera_view, name='delete_camera'),
    path('web/cameras/control/all/', views.control_all_cameras_view, name='control_all_cameras'),
    
    # Incluir todas las rutas de detection (streaming, APIs, etc.)
    path('detection/', include('detection.urls')),
]