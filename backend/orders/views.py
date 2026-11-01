from django.shortcuts import render
from django.db import IntegrityError, transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import F
from menu.models import Product
from .models import Order
from .serializers import OrderSerializer, OrderStatusChangeSerializer
from .permissions import IsOwnerOrStaff
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
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

    @extend_schema(
        summary='Создание нового заказа',
        description=(
                'Создаёт заказ покупателя и списывает продукты со склада. '
                'Для защиты от повторного оформления требуется заголовок '
                'Idempotency-Key.'
        ),
        parameters=[
            OpenApiParameter(
                name='Idempotency-Key',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.HEADER,
                required=True,
                description=(
                        'Уникальный ключ запроса длиной от 1 до 100 символов. '
                        'При повторении запроса с тем же ключом и данными '
                        'возвращается ранее созданный заказ.'
                ),
            ),
        ],
        request=OrderSerializer,
        responses={
            201: OrderSerializer,
            200: OrderSerializer,
            400: {'description': 'Некорректные данные заказа'},
            409: {'description': 'Ключ уже использован с другими данными'},
        },
    )


    def create(self, request, *args, **kwargs):
        # Получаем ключ идемпотентности из HTTP-запросов
        key = request.headers.get('Idempotency-Key')

        # Запрещаем создавать заказ без ключа идемпотентности
        if not key or not key.strip():
            return Response(
                {'detail': 'Idempotency-Key header is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Проверяем максимальную длину ключа
        if len(key) > 100:
            return Response(
           {'detail': 'Idempotency-Key must not exceed 100 characters.'},
                status=status.HTTP_400_BAD_REQUEST
            )

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
        # Когда Swagger анализирует API, возвращаем
        # базовый QuerySet только для генерации документации.
        if getattr(self, 'swagger_fake_view', False):
            return Order.objects.none()

        user = self.request.user

        # Неавторизованному пользователю заказы недоступны
        if not user.is_authenticated:
            return Order.objects.none()

        # Повар и администратор видят все заказы
        if user.role in ('COOK', 'ADMIN') or user.is_superuser:
            return Order.objects.all().order_by('-created_at')

        # Покупатель видит только собственные заказы
        return Order.objects.filter(
            customer=user
        ).order_by('-created_at')


    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        # Запрещаем удалять заказы, которые уже начали готовить
        if order.status != 'NEW':
            return Response(
                {'detail': 'Нельзя удалить заказ, который уже взят в работу.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

    def restore_order_stock(self, order):
        """Возвращает списанные порции при отмене заказа."""

        # Перебираем все позиции отменяемого заказа
        for item in order.items.all():
            # Возвращаем порции только для товаров
            # с ограниченным складским остатком
            Product.objects.filter(
                pk=item.product_id,
                quantity__isnull=False # не изменяем продукты с неограниченным остатком.
            ).update(
                quantity=F('quantity') + item.quantity # увеличиваем остаток непосредственно в PostgreSQL.
            )

    """ Декоракор для понятного и красивого Swagger """
    @extend_schema(
        summary='Отмена заказа покупателем',
        description=(
                'Позволяет покупателю отменить собственный заказ '
                'в статусе NEW или CONFIRMED. '
                'При отмене продукты возвращаются на склад. '
                'Повторная отмена запрещена.'
        ),
        request=None,
        responses={
            200: OrderSerializer,
            400: {'description': 'Заказ нельзя отменить'},
            403: {'description': 'Недостаточно прав'},
            404: {'description': 'Заказ не найден'},
        },
    )

    @action(detail=True, methods=['post']) # Создаёт API-операцию /api/orders/{id}/cancel/
    @transaction.atomic
    def cancel(self, request, pk=None):
        """Покупатель отменяет собственный заказ."""

        # Получаем заказ с учётом прав доступа
        order = self.get_object()

        # Отменять через этот метод может только владелец заказа
        if order.customer_id != request.user.id:
            return Response(
                {'detail': 'Можно отменять только собственные заказы.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Блокируем заказ от одновременных изменений
        order = Order.objects.select_for_update().get(pk=order.pk)

        # Отменять можно только до начала приготовления
        if order.status not in (
                Order.Status.NEW,
                Order.Status.CONFIRMED
        ):
            return Response(
                {'detail': 'Заказ уже нельзя отменить.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Возвращаем списанные порции на склад
        self.restore_order_stock(order)

        # Меняем статус заказа
        order.status = Order.Status.CANCELLED
        order.save(update_fields=['status', 'updated_at'])

        # Возвращаем обновлённый заказ
        serializer = self.get_serializer(order)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    @extend_schema(
        summary='Изменение статуса заказа',
        description=(
                'Изменять статус заказа могут только повар и администратор.\n\n'
                'Разрешённые переходы:\n'
                '- NEW → CONFIRMED или CANCELLED\n'
                '- CONFIRMED → COOKING или CANCELLED\n'
                '- COOKING → READY\n'
                '- READY → DELIVERING\n'
                '- DELIVERING → COMPLETED\n\n'
                'При отмене заказа продукты возвращаются на склад.'
        ),
        request=OrderStatusChangeSerializer,
        responses={
            200: OrderSerializer,
            400: {'description': 'Недопустимый переход статуса'},
            403: {'description': 'Недостаточно прав'},
            404: {'description': 'Заказ не найден'},
        },
    )

    @action(detail=True, methods=['post'])
    @transaction.atomic # Статус и остатки изменяются как одна операция
    def change_status(self, request, pk=None):
        """Изменение статуса заказа с возвратом остатков при отмене."""

        user = request.user

        # Только повар или администратор может менять статус
        if user.role not in ('COOK', 'ADMIN') and not user.is_superuser:
            return Response(
                {'detail': 'Только повар или администратор может менять статус заказа.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Получаем заказ с обычной проверкой доступа ViewSet
        order = self.get_object()

        # Блокируем заказ, чтобы две отмены не прошли одновременно
        order = Order.objects.select_for_update().get(pk=order.pk)

        new_status = request.data.get('status')

        # Разрешённые переходы
        allowed_transitions = {
            'NEW': ['CONFIRMED', 'CANCELLED'],
            'CONFIRMED': ['COOKING', 'CANCELLED'],
            'COOKING': ['READY'],
            'READY': ['DELIVERING'],
            'DELIVERING': ['COMPLETED'],
            'COMPLETED': [],
            'CANCELLED': [],
        }

        allowed = allowed_transitions.get(order.status, [])

        # Проверяем, разрешён ли переход
        if new_status not in allowed:
            return Response(
                {
                    'detail': 'Недопустимый переход статуса.',
                    'current_status': order.status,
                    'allowed_statuses': allowed
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Если отменяем заказ — возвращаем порции на склад
        # Возвращаем остатки при разрешённой отмене
        if new_status == 'CANCELLED':
            self.restore_order_stock(order)

        # Меняем статус заказа
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])

        serializer = self.get_serializer(order)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )