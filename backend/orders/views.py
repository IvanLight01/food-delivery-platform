from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Order
from .serializers import OrderSerializer
from .permissions import IsOwnerOrStaff

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsOwnerOrStaff, IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Повара и админы видят все заказы в системе
        if user.role in ('COOK', 'ADMIN') or user.is_superuser:
            return Order.objects.all().order_by('-created_at')
        # Клиенты видят только свои заказы
        return Order.objects.filter(customer=user).order_by('-created_at')

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        # Запрещаем удалять заказы, которые уже начали готовить
        if order.status != 'NEW':
            return Response(
                {'detail': 'Нельзя удалить заказ, который уже взят в работу.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)


    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        # Получаем заказ
        order = self.get_object()

        # Проверяем роль пользователя
        user = request.user

        if user.role not in ('COOK', 'ADMIN') and not user.is_superuser:
            return Response(
                {'detail': 'Только повар или администратор может менять статус заказа.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Получаем новый статус из JSON
        new_status = request.data.get('status')

        # Допустимые переходы
        allowed_transitions = {
            'NEW': ['CONFIRMED', 'CANCELLED'],
            'CONFIRMED': ['COOKING', 'CANCELLED'],
            'COOKING': ['READY', 'CANCELLED'],
            'READY': ['DELIVERING'],
            'DELIVERING': ['COMPLETED'],
            'COMPLETED': [],
            'CANCELLED': [],
        }

        # Проверяем допустимость перехода
        allowed = allowed_transitions.get(order.status, [])

        if new_status not in allowed:
            return Response(
                {
                    'detail': 'Недопустимый переход статуса.',
                    'current_status': order.status,
                    'allowed_statuses': allowed
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Сохраняем новый статус
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])

        # Возвращаем обновлённый заказ
        serializer = self.get_serializer(order)

        return Response(serializer.data, status=status.HTTP_200_OK)