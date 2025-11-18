from django.urls import path
from . import views

urlpatterns = [
    # Vistas HTML
    path('web/login/', views.login_page, name='login_page'),
    path('web/login/submit/', views.login_submit, name='login_submit'),
    path('web/logout/', views.logout_view, name='logout'),
    path('web/dashboard/', views.dashboard, name='dashboard'),
    path('web/cameras/add/', views.add_camera_web, name='add_camera_web'),
    path('web/cameras/<str:camera_sanitized_name>/control/', views.control_camera_web, name='control_camera_web'),
    path('web/cameras/<str:camera_sanitized_name>/remove/', views.remove_camera_web, name='remove_camera_web'),
    path('web/cameras/control-all/', views.control_all_web, name='control_all_web'),
    
    # APIs públicas
    path('stream/<str:camera_sanitized_name>/', views.video_feed, name='video-feed'),
    path('health/', views.health_check, name='health-check'),
    
    # Root - redirige al login
    path('', views.login_page, name='api-root'),
]