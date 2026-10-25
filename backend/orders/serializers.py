from rest_framework import serializers
from .models import Order, OrderItem
from django.db import transaction
from menu.models import Product



class OrderItemSerializer(serializers.ModelSerializer):
    # line_total — это @property в модели, но всё равно объявим явно,
    # чтобы формат был строкой с 2 знаками после точки (для денег).
    line_total = serializers.SerializerMethodField()
    quantity = serializers.IntegerField(min_value=1)

    class Meta:
        model = OrderItem
        fields = (
            'id',
            'product',  # id блюда (для ссылки)
            'product_name',  # имя на момент покупки (сохранено в модели)
            'price',  # цена на момент покупки
            'quantity',
            'line_total',  # price × quantity
        )
        read_only_fields = ('product_name', 'price', 'line_total')

    def get_line_total(self, obj):
        # obj.line_total — это @property из модели. Возвращаем как строку.
        return f'{obj.line_total:.2f}'


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, allow_empty=False)  # Позволяет отправлять заказ вместе с позициями в одном JSON

    class Meta:
        model = Order
        fields = (
            'id',
            'customer',
            'delivery_address',
            'status',
            'total_price',  # Запятая исправлена!
            'items',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('customer', 'status', 'total_price', 'created_at', 'updated_at')



    def validate_items(self, items):
        # Проверяем каждое блюдо в заказе
        for item in items:
            product = item['product']

            # Нельзя заказывать блюда, снятые с продажи
            if not product.is_active:
                raise serializers.ValidationError(
                    f'Блюдо "{product.name}" недоступно для заказа.'
                )

        return items


    """
        @transaction.atomic гарантирует, что связанные операции с базой данных выполняются как единое целое:
        если создание заказа завершится ошибкой, изменения внутри транзакции будут отменены.
    """
    @transaction.atomic # обеспечивает принцип «либо всё, либо ничего»
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        # Извлекаем пользователя из контекста запроса
        user = self.context['request'].user

        # Создаем пустой заказ
        order = Order.objects.create(customer=user, **validated_data)

        total_price = 0
        order_items_to_create = []

        # Обрабатываем каждую позицию в заказе
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']

            # Подтягиваем актуальную цену и название из меню
            current_price = product.price
            current_name = product.name

            total_price += current_price * quantity

            order_items_to_create.append(
                OrderItem(
                    order=order,
                    product=product,
                    product_name=current_name,
                    price=current_price,
                    quantity=quantity
                )
            )

        # Массовое сохранение позиций в БД за один запрос (Оптимизация производительности)
        OrderItem.objects.bulk_create(order_items_to_create)

        # Сохраняем финальную стоимость в заказ
        order.total_price = total_price
        order.save()

        # Возвращаем созданный объект DRF.
        return order



    @transaction.atomic
    def update(self, instance, validated_data):
        # Получаем позиции из запроса, если они переданы
        items_data = validated_data.pop('items', None)

        # Обновляем обычные поля, например адрес доставки
        for field, value in validated_data.items():
            setattr(instance, field, value)

        # Если список блюд передан, обновляем состав заказа
        if items_data is not None:
            total_price = 0
            new_items = []

            for item_data in items_data:
                product = item_data['product']
                quantity = item_data['quantity']

                # Используем актуальную цену из базы данных
                total_price += product.price * quantity

                new_items.append(
                    OrderItem(
                        order=instance,
                        product=product,
                        product_name=product.name,
                        price=product.price,
                        quantity=quantity
                    )
                )

            # Удаляем старые позиции
            instance.items.all().delete()

            # Сохраняем новые позиции
            OrderItem.objects.bulk_create(new_items)

            # Обновляем итоговую стоимость
            instance.total_price = total_price

        # Сохраняем изменения заказа
        instance.save()

        return instance