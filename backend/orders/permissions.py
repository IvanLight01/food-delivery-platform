
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrStaff(BasePermission):
    """
    Клиент может просматривать свои заказы.
    Клиент может изменять свой заказ только в статусе NEW.
    Повар и администратор могут просматривать все заказы.
    Изменять статус могут только повар и администратор.
    """

    def has_permission(self, request, view):
        user = request.user

        # Неавторизованные пользователи не допускаются
        if not user or not user.is_authenticated:
            return False

        # Изменение статуса доступно только персоналу
        if view.action == 'change_status':
            return (
                user.role in ('COOK', 'ADMIN')
                or user.is_superuser
            )

        return True

    def has_object_permission(self, request, view, obj):
        #print("=== ПРОВЕРКА ПРАВ ===")
        #print("Пользователь:", request.user.username)
        #print("Действие:", view.action)
        #print("Статус заказа:", obj.status)


        user = request.user

        is_staff = (
            user.role in ('COOK', 'ADMIN')
            or user.is_superuser
        )

        # Запрещаем обычное редактирование и удаление заказов, которые уже взяты в работу
        if view.action in ('update', 'partial_update', 'destroy'):
            if obj.status != 'NEW':
                return False

        # Повар и администратор имеют доступ к заказам
        if is_staff:
            return True

        # Клиент может работать только со своим заказом
        if obj.customer_id != user.id:
            return False

        # Просмотр собственного заказа разрешён
        if request.method in SAFE_METHODS:
            return True

        # Изменение статуса клиенту запрещено
        if view.action == 'change_status':
            return False

        # Изменение и удаление — только пока заказ NEW
        if view.action in ('update', 'partial_update', 'destroy'):
            return obj.status == 'NEW'

        return False