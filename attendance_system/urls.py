from django.urls import path
from detection import views

urlpatterns = [
    path('cameras/add/', views.add_camera_view),
    path('cameras/<str:camera_id>/start/', views.start_camera_view),
    path('cameras/<str:camera_id>/stop/', views.stop_camera_view),
    path('cameras/<str:camera_id>/status/', views.camera_status_view),
    path('cameras/<str:camera_id>/frame/', views.camera_frame_view),
    path('cameras/<str:camera_id>/remove/', views.remove_camera_view),
    path('cameras/all/', views.all_cameras_view),
    path('cameras/<str:camera_id>/detections/', views.camera_detections_view),
]
# attendance_system/settings.py