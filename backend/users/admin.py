from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from users.models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Настройка отображения пользователей
    в стандартной Django Admin-панели.
    """

    list_display = (
        'username',
        'email',
        'first_name',
        'last_name',
        'role',
        'is_active',
        'created_at',
    )

    list_filter = (
        'role',
        'is_active',
        'is_staff',
    )

    search_fields = (
        'username',
        'email',
        'first_name',
        'last_name',
        'phone',
    )

    fieldsets = UserAdmin.fieldsets + (
        (
            'Дополнительная информация',
            {
                'fields': (
                    'phone',
                    'role',
                    'created_at',
                )
            }
        ),
    )

    readonly_fields = (
        'created_at',
    )
