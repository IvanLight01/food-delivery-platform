"""Определяет, что произойдёт, когда приходит HTTP-запрос"""

from rest_framework import status
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .serializers import RegisterSerializer
from rest_framework.views import APIView


class RegisterView(generics.CreateAPIView):
    """
    Регистрация нового клиента.
    """

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

class MeView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated] # говорит Django - Пускать сюда только пользователя, который успешно прошёл JWT-аутентификацию.

    # После проверки JWT DRF сам определяет пользователя и помещает его сюда
    def get(self, request):
        return Response({
            'username': request.user.username,
            'email': request.user.email,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'role': request.user.role,
        })


class LogoutView(APIView):
    # Выход доступен только авторизованному пользователю.
    permission_classes = [IsAuthenticated]

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
