"""Преобразует данные между JSON и Python/Django-моделями"""

from django.contrib.auth import get_user_model
from rest_framework import serializers


User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """
    Сериализатор регистрации нового пользователя.

    Пароль принимается отдельно и передаётся в set_password(),
    чтобы он сохранился в базе в виде хеша, а не обычного текста.
    """

    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    password_confirm = serializers.CharField(
        write_only=True,
        min_length=8
    )

    class Meta:
        model = User
        fields = (
            'username',
            'email',
            'password',
            'password_confirm',
            'first_name',
            'last_name',
            'phone',
        )

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password': 'Пароли не совпадают.'
            })

        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')

        password = validated_data.pop('password')

        user = User(**validated_data)

        # Пароль обязательно сохраняем через set_password(),
        # иначе он попадёт в БД в открытом виде.
        user.set_password(password)

        user.save()

        return user

class ProfileSerializer(serializers.ModelSerializer):
    """Просмотр и редактирование профиля пользователя."""

    class Meta:
        model = User

        fields = (
            'username',
            'email',
            'first_name',
            'last_name',
            'phone',
            'role',
        )

        # Эти поля нельзя менять через редактирование профиля
        read_only_fields = (
            'username',
            'email',
            'role',
        )