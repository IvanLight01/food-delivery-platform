"""Связывает URL с View"""

from django.urls import path
from .views import RegisterView, MeView, LogoutView
from rest_framework_simplejwt.views import (
    TokenObtainPairView, # получает JSON  и возвращает пару токенов
    TokenRefreshView, # получает refresh и выдаёт новый access
)


urlpatterns = [
    path(
        'register/', RegisterView.as_view(), name='register'
    ),

    path(
        'login/', TokenObtainPairView.as_view(), name='login'
    ),

    path(
        'refresh/', TokenRefreshView.as_view(), name='token_refresh'
    ),

    path('me/', MeView.as_view(), name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
]