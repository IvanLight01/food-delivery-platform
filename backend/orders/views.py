from django.shortcuts import render
from django.db import IntegrityError, transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Order
from .serializers import OrderSerializer
from .permissions import IsOwnerOrStaff
import hashlib
import json

""" Функция вычисления хеша """
def calculate_request_hash(data):
    # Преобразуем данные в JSON с одинаковым порядком ключей
    json_string = json.dumps(
        data,
        sort_keys=True, # обеспечивает одинаковый порядок ключей.
        ensure_ascii=False,
        separators=(',', ':')
    )

    # Преобразуем строку JSON в байты
    encoded_data = json_string.encode('utf-8')

    # Вычисляем отпечаток SHA-256
    return hashlib.sha256(encoded_data).hexdigest() # возвращает полученный хеш в удобном текстовом формате

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsOwnerOrStaff, IsAuthenticated]

    def find_order_by_key(self, key):
        return Order.objects.filter(
            customer=self.request.user,
            idempotency_key=key
        ).first()

    def create(self, request, *args, **kwargs):
        # Получаем ключ идемпотентности из HTTP-запросов
        key = request.headers.get('Idempotency-Key')

        if key:
            existing_order = self.find_order_by_key(key)

            if existing_order:
                new_hash = calculate_request_hash(request.data)

                if existing_order.request_hash != new_hash:
                    return Response(
                        {'detail': 'Этот ключ уже использован для другого заказа.'},
                        status=status.HTTP_409_CONFLICT
                    )

                serializer = self.get_serializer(existing_order)

                return Response(
                    serializer.data,
                    status=status.HTTP_200_OK
                )

        try:
            with transaction.atomic():
                return super().create(request, *args, **kwargs)

        except IntegrityError:
            # Если ключ отсутствует, ошибка не связана
            # с повторным использованием ключа
            if not key:
                raise

            # После отката транзакции повторно ищем заказ
            existing_order = Order.objects.filter(
                customer=request.user,
                idempotency_key=key
            ).first()

            # Если заказ не найден, причина ошибки другая
            if existing_order is None:
                raise

            # Проверяем содержимое повторного запроса
            new_hash = calculate_request_hash(request.data)

            if existing_order.request_hash != new_hash:
                return Response(
                    {'detail': 'Этот ключ уже использован для другого заказа.'},
                    status=status.HTTP_409_CONFLICT
                )

            # Возвращаем существующий заказ
            serializer = self.get_serializer(existing_order)

            return Response(
                serializer.data,
                status=status.HTTP_200_OK
            )


    def perform_create(self, serializer):
        # Передаём ключ сериализатору
        key = self.request.headers.get('Idempotency-Key')

        # Вычисляем отпечаток содержимого запроса
        request_hash = calculate_request_hash(self.request.data)

        # Сохраняем заказ вместе с ключом и отпечатком
        serializer.save(
            idempotency_key=key,
            request_hash=request_hash
        )

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