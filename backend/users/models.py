"""Описывает структуру данных"""

from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
        Основная модель пользователя платформы.

        Один пользователь может иметь одну из трёх ролей:
        CUSTOMER — клиент,
        COOK — повар,
        ADMIN — администратор.
        """
    class Role(models.TextChoices):
        CUSTOMER = 'CUSTOMER', 'Клиент'
        COOK = 'COOK', 'Повар'
        ADMIN = 'ADMIN', 'Администратор'

    email = models.EmailField(
        unique=True,
        verbose_name='Электронная почта')

    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Телефон'
    )

    first_name = models.CharField(
        max_length=150,
        verbose_name='Имя'
    )

    last_name = models.CharField(
        max_length=150,
        verbose_name='Фамилия'
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
        verbose_name='Роль'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата регистрации'
    )

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'