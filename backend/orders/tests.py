""" УЧУ DJANGO САМОСТОЯТЕЛЬНО ИСКАТЬ ОШИБКИ """
# В терминале:
# E — ошибка выполнения теста.
# F — тест выполнился, но проверка не прошла.
# . — тест успешно пройден.

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from decimal import Decimal
from .models import Order, OrderItem
from menu.models import Category, Product


User = get_user_model()


class OrderPermissionTests(TestCase):

    def setUp(self):
        # Создаём тестового повара
        self.cook = User.objects.create_user(
            username='test_cook',
            email='cook@test.example',
            password='TestPassword123!',
            role='COOK'
        )

        # Создаём тестового клиента
        self.customer = User.objects.create_user(
            username='test_customer',
            email='customer@test.example',
            password='TestPassword123!',
            role='CUSTOMER'
        )

        # Второй клиент — посторонний пользователь
        self.other_customer = User.objects.create_user(
            username='other_customer',
            email='other_customer@test.example',
            password='TestPassword123!',
            role='CUSTOMER'
        )

        # Создаём завершённый заказ
        self.order = Order.objects.create(
            customer=self.customer,
            delivery_address='Старый адрес',
            status='COMPLETED'
        )

        # Создаём клиент для отправки API-запросов
        self.client = APIClient()

    """ Запрет изменения завершённого заказа """
    def test_cook_cannot_edit_completed_order(self):
        # Авторизуемся как повар
        self.client.force_authenticate(user=self.cook) # force_authenticate(user=self.cook) — позволяет тестовому API-клиенту
                                                       # выполнять запросы от имени повара без отдельного получения JWT.
                                                       # Так мы проверяем именно права доступа.

        # Пытаемся изменить завершённый заказ
        response = self.client.patch(
            f'/api/orders/{self.order.id}/',
            {'delivery_address': 'Новый адрес'},
            format='json'
        )

        # Проверяем, что Django запретил изменение
        self.assertEqual(response.status_code, 403)

        # Проверяем данные непосредственно в базе
        # Мы проверяем не только ответ сервера, но и то, что данные действительно не изменились.
        self.order.refresh_from_db()

        self.assertEqual(
            self.order.delivery_address,
            'Старый адрес'
        )


    """ Запрет смены статуса клиентом """
    def test_customer_cannot_change_order_status(self):
        # Авторизуемся как клиент
        self.client.force_authenticate(user=self.customer)

        # Пытаемся изменить статус заказа
        response = self.client.post(
            f'/api/orders/{self.order.id}/change_status/',
            {'status': 'COOKING'},
            format='json'
        )

        # Клиенту запрещено управлять статусами
        self.assertEqual(response.status_code, 403)

        # Проверяем, что статус в базе не изменился
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'COMPLETED')


    """ Защита чужих заказов """
    def test_customer_cannot_view_other_customer_order(self):
        # Авторизуемся как посторонний клиент
        self.client.force_authenticate(
            user=self.other_customer
        )

        # Пытаемся просмотреть чужой заказ
        response = self.client.get(
            f'/api/orders/{self.order.id}/'
        )

        # Чужой заказ не должен быть доступен
        self.assertEqual(response.status_code, 404)


    """ Пересчёт стоимости при изменении количества """
    def test_customer_can_update_new_order(self):
        # 1. Создаём категорию и блюдо
        category = Category.objects.create(
            name='Основные блюда'
        )

        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            is_active=True
        )

        # 2. Создаём новый заказ клиента
        order = Order.objects.create(
            customer=self.customer,
            delivery_address='Старый адрес',
            status='NEW',
            total_price=Decimal('1800.00')
        )

        # 3. Добавляем две порции лазаньи
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            price=product.price,
            quantity=2
        )

        # 4. Авторизуемся как владелец заказа
        self.client.force_authenticate(
            user=self.customer
        )

        # 5. Клиент меняет количество на три
        response = self.client.patch(
            f'/api/orders/{order.id}/',
            {
                'items': [
                    {
                        'product': product.id,
                        'quantity': 3
                    }
                ]
            },
            format='json'
        )

        # 6. Проверяем HTTP-ответ
        self.assertEqual(response.status_code, 200)

        # 7. Проверяем что новая стоимость сохранилась в PostgreSQL
        order.refresh_from_db()

        self.assertEqual(
            order.total_price,
            Decimal('2700.00')
        )

        # 8. Проверяем количество порций
        item = order.items.get()

        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.price, Decimal('900.00'))


    """ Запрет заказа недоступного блюда """
    def test_cannot_order_inactive_product(self):
        # Создаём категорию
        category = Category.objects.create(
            name='Основные блюда'
        )

        # Создаём блюдо, недоступное для заказа
        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            is_active=False
        )

        # Авторизуемся как клиент
        self.client.force_authenticate(
            user=self.customer
        )

        # Пытаемся создать заказ
        response = self.client.post(
            '/api/orders/',
            {
                'delivery_address': 'Тестовый адрес',
                'items': [
                    {
                        'product': product.id,
                        'quantity': 2
                    }
                ]
            },
            format='json'
        )

        # Django должен отклонить заказ
        self.assertEqual(response.status_code, 400)

        # Проверяем, что заказ не создан
        self.assertEqual(
            Order.objects.filter(
                customer=self.customer,
                status='NEW'
            ).count(),
            0
        )


    """ Запрет отрицательного количества """
    def test_cannot_order_negative_quantity(self):
        # Создаём категорию
        category = Category.objects.create(
            name='Основные блюда'
        )

        # Создаём доступное блюдо
        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            is_active=True
        )

        # Авторизуемся как клиент
        self.client.force_authenticate(
            user=self.customer
        )

        # Запоминаем количество заказов до запроса
        orders_before = Order.objects.count()

        # Отправляем недопустимое количество
        response = self.client.post(
            '/api/orders/',
            {
                'delivery_address': 'Тестовый адрес',
                'items': [
                    {
                        'product': product.id,
                        'quantity': -5
                    }
                ]
            },
            format='json'
        )

        # Проверяем, что сервер отклонил запрос
        self.assertEqual(response.status_code, 400)

        # Проверяем, что заказ не появился в БД
        self.assertEqual(
            Order.objects.count(),
            orders_before
        )


    """ Защита от подмены цены """
    def test_customer_cannot_override_order_price(self):
        # Создаём категорию
        category = Category.objects.create(
            name='Основные блюда'
        )

        # Создаём лазанью с настоящей ценой
        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            is_active=True
        )

        # Авторизуемся как клиент
        self.client.force_authenticate(user=self.customer)

        # Отправляем заказ с подменённой ценой
        response = self.client.post(
            '/api/orders/',
            {
                'delivery_address': 'Тестовый адрес',
                'total_price': '2.00',
                'items': [
                    {
                        'product': product.id,
                        'quantity': 2,
                        'price': '1.00'
                    }
                ]
            },
            format='json'
        )

        # Заказ должен успешно создаться
        self.assertEqual(response.status_code, 201)

        # Проверяем стоимость, сохранённую в БД
        order = Order.objects.get(id=response.data['id'])

        self.assertEqual(
            order.total_price,
            Decimal('1800.00')
        )

        # Проверяем цену позиции заказа
        item = order.items.get()

        self.assertEqual(
            item.price,
            Decimal('900.00')
        )
