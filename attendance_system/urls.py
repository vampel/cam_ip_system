from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from detection import views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Redirigir raíz a login personalizado
    path('', lambda request: redirect('/api/web/login/')),
    
    # Redirigir accounts/login/ de Django a tu sistema
    path('accounts/login/', lambda request: redirect('/api/web/login/')),
    
    # Tus URLs existentes
    path('login/', views.login_page, name='login_page'),
    path('login/submit/', views.login_submit, name='login_submit'),
    path('logout/', views.logout_view, name='logout_view'),
    path('api/', include('detection.urls')),
]