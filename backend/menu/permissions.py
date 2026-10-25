from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsCookOrAdminOrReadOnly(BasePermission):
    """
    Все могут просматривать меню.
    Создавать, изменять и удалять блюда могут только повар и администратор.
    """

    def has_permission(self, request, view):
        # GET, HEAD и OPTIONS разрешены всем, включая гостей.
        if request.method in SAFE_METHODS:
            return True

        # Для изменения меню нужна авторизация.
        user = request.user

        if not user or not user.is_authenticated:
            return False

        # Разрешаем изменение меню повару и администратору.
        return (
            user.role in ('COOK', 'ADMIN')
            or user.is_superuser
        )
