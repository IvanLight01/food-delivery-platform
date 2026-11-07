"""Определяет, что произойдёт, когда приходит HTTP-запрос"""

from rest_framework import status
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .serializers import RegisterSerializer, ProfileSerializer
from rest_framework.views import APIView
from rest_framework import serializers
from drf_spectacular.utils import extend_schema


class RegisterView(generics.CreateAPIView):
    """
    Регистрация нового клиента.
    """

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

""" Описывает данные, которые сервер возвращает клиенту """
class MeResponseSerializer(serializers.Serializer):
    """Описание данных текущего пользователя для Swagger."""

    username = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.CharField()

""" Клиент может использовать GET, PATCH, PUT благодаря RetrieveUpdateAPIView """
class MeView(generics.RetrieveUpdateAPIView):
    """Просмотр и редактирование собственного профиля."""

    permission_classes = [IsAuthenticated] # Только авторизованный пользователь
    serializer_class = ProfileSerializer # Сериализатор определяет доступные для изменения поля

    def get_object(self):
        # Возвращаем только текущего пользователя с подтвержденными JWT-токенами
        return self.request.user


''' Описывает данные, которые клиент отправляет серверу '''
class LogoutRequestSerializer(serializers.Serializer):
    """Данные, необходимые для выхода из аккаунта."""

    refresh = serializers.CharField() # Refresh-токен, который необходимо отозвать


class LogoutView(APIView):
    # Выход доступен только авторизованному пользователю.
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Выход из аккаунта',
        description='Отзывает refresh-токен текущего пользователя.',
        request=LogoutRequestSerializer,
        responses={
            200: {'type': 'object', 'properties': {
                'detail': {'type': 'string'}
            }},
            400: {'type': 'object', 'properties': {
                'detail': {'type': 'string'}
            }},
        },
    )

    def post(self, request):
        # Клиент передаёт Refresh Token в JSON.
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response(
                {'detail': 'Не передан refresh-токен.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)

            # Помечаем Refresh Token как отозванный.
            token.blacklist()

        except TokenError:
            return Response(
                {'detail': 'Токен недействителен или уже отозван.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {'detail': 'Выход выполнен.'},
            status=status.HTTP_200_OK,
        )
