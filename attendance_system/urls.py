# attendance_system/urls.py
from django.contrib import admin
from django.urls import path
from detection import views

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Vistas HTML (Web)
    path('', views.login_page, name='api-root'),
    path('web/login/', views.login_page, name='login_page'),
    path('web/login/submit/', views.login_submit, name='login_submit'),
    path('web/logout/', views.logout_view, name='logout_view'),
    path('web/dashboard/', views.dashboard, name='dashboard'),
    path('web/cameras/add/', views.add_camera_view, name='add_camera_web'),
    path('web/cameras/<str:camera_sanitized_name>/control/', views.control_camera_web, name='control_camera_web'),
    path('web/cameras/<str:camera_sanitized_name>/remove/', views.remove_camera_view, name='remove_camera_web'),
    path('web/cameras/control-all/', views.control_all_web, name='control_all_web'),
    
    # APIs para cámaras
    path('api/cameras/all/', views.all_cameras_view, name='all_cameras_view'),
    path('api/cameras/add/', views.add_camera_view, name='add_camera_view'),
    path('api/cameras/<str:camera_id>/start/', views.start_camera_view, name='start_camera_view'),
    path('api/cameras/<str:camera_id>/stop/', views.stop_camera_view, name='stop_camera_view'),
    path('api/cameras/<str:camera_id>/status/', views.camera_status_view, name='camera_status_view'),
    path('api/cameras/<str:camera_id>/frame/', views.camera_frame_view, name='camera_frame_view'),
    path('api/cameras/<str:camera_id>/remove/', views.remove_camera_view, name='remove_camera_view'),
    path('api/cameras/<str:camera_id>/detections/', views.camera_detections_view, name='camera_detections_view'),
]