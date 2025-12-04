# dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('api/cameras/add/', views.add_camera_view, name='add_camera'),
    path('api/cameras/<str:camera_id>/start/', views.start_camera_view, name='start_camera'),
    path('api/cameras/<str:camera_id>/stop/', views.stop_camera_view, name='stop_camera'),
    path('api/cameras/<str:camera_id>/status/', views.camera_status_view, name='camera_status'),
    path('api/cameras/<str:camera_id>/frame/', views.camera_frame_view, name='camera_frame'),
    path('api/cameras/<str:camera_id>/remove/', views.remove_camera_view, name='remove_camera'),
    path('api/cameras/all/', views.all_cameras_view, name='all_cameras'),
    path('api/cameras/<str:camera_id>/detections/', views.camera_detections_view, name='camera_detections'),
    path('', views.dashboard, name='dashboard'),
]