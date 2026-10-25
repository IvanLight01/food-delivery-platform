from django.db import models
from django.conf import settings


""" ЗАКАЗ КЛИЕНТА """
class Order(models.Model):

    class Status(models.TextChoices):
        NEW = 'NEW', 'Новый'
        CONFIRMED = 'CONFIRMED', 'Подтверждён'
        COOKING = 'COOKING', 'Готовится'
        READY = 'READY', 'Готов'
        DELIVERING = 'DELIVERING', 'Доставляется'
        COMPLETED = 'COMPLETED', 'Завершён'
        CANCELLED = 'CANCELLED', 'Отменён'

    # Кто оформил заказ.
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name='Клиент',
    )

    # Адрес пока храним обычным текстом.
    delivery_address = models.TextField(
        verbose_name='Адрес доставки',
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        verbose_name='Статус',
    )

    # Итоговая сумма заказа.
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Стоимость заказа',
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания',
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата изменения',
    )

    def __str__(self):
        return f'Заказ №{self.pk} — {self.customer.username}'


""" Определённое блюдо и его количество """
class OrderItem(models.Model):

    # К какому заказу относится позиция.
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE, # позиции удаляются вместе с заказом
        related_name='items',
        verbose_name='Заказ',
    )

    # Какое блюдо заказали.
    product = models.ForeignKey(
        'menu.Product',
        on_delete=models.PROTECT,
        related_name='order_items',
        verbose_name='Блюдо',
    )

    # Сохраняем название на момент покупки.
    product_name = models.CharField(
        max_length=200,
        verbose_name='Название блюда при покупке',
    )

    # Сохраняем цену на момент покупки.
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Цена при покупке',
    )

    quantity = models.PositiveIntegerField(
        verbose_name='Количество',
    )

    def __str__(self):
        return f'{self.product_name} × {self.quantity}'

    @property
    def line_total(self):
        return self.price * self.quantity