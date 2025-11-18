from django.contrib import admin
from django.urls import path, include
from detection import views  # ← Agregar esta importación

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Ruta raíz - redirige al dashboard o login
    path('', views.dashboard, name='dashboard'),
    
    # URLs de autenticación directas
    path('login/', views.login_page, name='login_page'),
    path('login/submit/', views.login_submit, name='login_submit'),
    path('logout/', views.logout_view, name='logout_view'),
    
    # APIs bajo /api/
    path('api/', include('detection.urls')),
]