# ai_image_app/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('creation/', views.creation, name='creation'),
    path('agreement/', views.agreement, name='agreement'),
    path('profile/', views.profile, name='profile'),
    path('login/', views.login, name='login'),
    path('signup/', views.signup, name='signup'),
    path('generate_image/', views.generate_image, name='generate_image'),
    path('check_status/', views.check_status, name='check_status'),
]