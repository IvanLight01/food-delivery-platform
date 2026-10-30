""" УЧУ DJANGO САМОСТОЯТЕЛЬНО ИСКАТЬ ОШИБКИ """
# В терминале:
# E — ошибка выполнения теста.
# F — тест выполнился, но проверка не прошла.
# . — тест успешно пройден.

from django.test import TestCase, TransactionTestCase
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.db import close_old_connections
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from decimal import Decimal
from .models import Order, OrderItem
from .views import OrderViewSet
from menu.models import Category, Product


User = get_user_model()

""" Тесты на определение разрешений """
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

        # Создаём инструмент APIClient для отправки API-запросов
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
            format='json',
            HTTP_IDEMPOTENCY_KEY = 'price-protection-test-123' # отправляем запрос с ключом, чтоб тест проверял именно цену, а не отсутстствие заголовка с ключом
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

    """ Защита от создания заказа без Idempotency-Key
        и проверка, что кол-во заказов не изменилось """
    def test_create_order_without_idempotency_key_returns_400(self):
        """Без Idempotency-Key заказ не должен создаваться."""

        category = Category.objects.create(
            name='Основные блюда'
        )

        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            is_active=True
        )

        self.client.force_authenticate(user=self.customer)

        data = {
            'delivery_address': 'ул. Пушкина, 10',
            'items': [
                {
                    'product': product.id,
                    'quantity': 2
                }
            ]
        }

        count_before = Order.objects.count()

        # Намеренно НЕ передаём HTTP_IDEMPOTENCY_KEY
        response = self.client.post(
            '/api/orders/',
            data,
            format='json'
        )

        # Сервер должен отклонить запрос
        self.assertEqual(response.status_code, 400)

        # В базе не должно появиться нового заказа
        self.assertEqual(
            Order.objects.count(),
            count_before
        )


    """ Запрет на создание заказа, если был обнаружен ключ из пробелов """
    def test_create_order_with_blank_idempotency_key_returns_400(self):
        """Ключ из пробелов не должен разрешать создание заказа."""

        self.client.force_authenticate(user=self.customer)

        count_before = Order.objects.count()

        response = self.client.post(
            '/api/orders/',
            {
                'delivery_address': 'ул. Пушкина, 10',
                'items': []
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY='   '
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            Order.objects.count(),
            count_before
        )

        self.assertEqual(
            response.data['detail'],
            'Idempotency-Key header is required.'
        )

    """ Тестирование граничного значения ключа """
    def test_create_order_with_too_long_idempotency_key_returns_400(self):
        """Ключ длиннее 100 символов должен отклоняться."""

        self.client.force_authenticate(user=self.customer)

        # Создаём ключ длиной 101 символ
        long_key = 'a' * 101

        count_before = Order.objects.count()

        response = self.client.post(
            '/api/orders/',
            {
                'delivery_address': 'ул. Пушкина, 10',
                'items': []
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY=long_key
        )

        # Сервер должен отклонить слишком длинный ключ
        self.assertEqual(response.status_code, 400)

        # Заказ не должен появиться в базе
        self.assertEqual(
            Order.objects.count(),
            count_before
        )

        # Проверяем конкретную причину ошибки
        self.assertEqual(
            response.data['detail'],
            'Idempotency-Key must not exceed 100 characters.'
        )

    """ Проверяет: успешное создание заказа,
        появление одной записи в базе 
        и сохранение полного ключа без обрезания """
    def test_create_order_with_100_character_idempotency_key(self):
        """Ключ длиной ровно 100 символов должен приниматься."""

        # Подготавливаем блюдо
        category = Category.objects.create(
            name='Основные блюда'
        )

        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            is_active=True
        )

        # Авторизуем покупателя
        self.client.force_authenticate(user=self.customer)

        # Создаём ключ ровно из 100 символов
        key = 'a' * 100

        count_before = Order.objects.count()

        response = self.client.post(
            '/api/orders/',
            {
                'delivery_address': 'ул. Пушкина, 10',
                'items': [
                    {
                        'product': product.id,
                        'quantity': 2
                    }
                ]
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY=key
        )

        # Запрос должен успешно создать заказ
        self.assertEqual(response.status_code, 201)

        # Проверяем, что появился ровно один заказ
        self.assertEqual(
            Order.objects.count(),
            count_before + 1
        )

        # Проверяем, что ключ сохранился полностью
        order = Order.objects.get(id=response.data['id'])
        self.assertEqual(order.idempotency_key, key)


    """ Защита от повторного последовательного запроса """
    def test_repeated_order_request_returns_same_order(self):
            """Повторный запрос с тем же ключом не должен создавать второй заказ."""
            # Создаём категорию и блюдо
            category = Category.objects.create(
                name='Основные блюда'
            )

            product = Product.objects.create(
                category=category,
                name='Лазанья',
                price=Decimal('900.00'),
                is_active=True
            )

            # Авторизуем клиента
            self.client.force_authenticate(user=self.customer)

            # Данные заказа
            data = {
                'delivery_address': 'ул. Пушкина, 10',
                'items': [
                    {
                        'product': product.id,
                        'quantity': 2
                    }
                ]
            }

            # Запоминаем количество существующих заказов
            count_before = Order.objects.filter(
                customer=self.customer
            ).count()

            # Отправляем первый запрос
            response1 = self.client.post(
                '/api/orders/',
                data,
                format='json',
                HTTP_IDEMPOTENCY_KEY='test-order-123'
            )

            # Повторяем запрос с тем же ключом
            response2 = self.client.post(
                '/api/orders/',
                data,
                format='json',
                HTTP_IDEMPOTENCY_KEY='test-order-123'
            )

            # Проверяем ответы
            self.assertEqual(response1.status_code, 201)
            self.assertEqual(response2.status_code, 200)

            # Оба ответа должны указывать на один заказ
            self.assertEqual(
                response1.data['id'],
                response2.data['id']
            )

            # Проверяем количество заказов в базе
            count_after = Order.objects.filter(
                customer=self.customer
            ).count()

            self.assertEqual(count_after, count_before + 1)

    """ Ответ 409 при повторном ключе с другими данными """
    def test_same_key_with_different_data_returns_409(self):
        """Один ключ нельзя использовать для разных заказов."""
        category = Category.objects.create(
            name='Основные блюда'
        )

        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            is_active=True
        )

        self.client.force_authenticate(user=self.customer)

        first_data = {
            'delivery_address': 'ул. Пушкина, 10',
            'items': [
                {'product': product.id, 'quantity': 2}
            ]
        }

        second_data = {
            'delivery_address': 'ул. Пушкина, 10',
            'items': [
                {'product': product.id, 'quantity': 5}
            ]
        }

        count_before = Order.objects.count()

        response1 = self.client.post(
            '/api/orders/',
            first_data,
            format='json',
            HTTP_IDEMPOTENCY_KEY='conflict-test-123'
        )

        response2 = self.client.post(
            '/api/orders/',
            second_data,
            format='json',
            HTTP_IDEMPOTENCY_KEY='conflict-test-123'
        )

        self.assertEqual(response1.status_code, 201)
        self.assertEqual(response2.status_code, 409)

        self.assertEqual(
            Order.objects.count(),
            count_before + 1
        )


""" Тесты на параллельное выполнение заказов """
class OrderConcurrencyTests(TransactionTestCase):
    """
    Проверяем создание заказов при одновременных запросах.

    """

    def setUp(self):
        self.customer = User.objects.create_user(
            username='concurrent_customer',
            email='concurrent@test.example',
            password='TestPassword123!',
            role='CUSTOMER'
        )

        self.category = Category.objects.create(
            name='Основные блюда'
        )

        self.product = Product.objects.create(
            category=self.category,
            name='Лазанья',
            price=Decimal('900.00'),
            is_active=True
        )

    def send_order(self, barrier):
        # Подготавливаем подключение к базе для потока
        close_old_connections()

        try:
            # Создаём отдельный APIClient
            client = APIClient() # каждый поток создаёт собственный клиент
            client.force_authenticate(user=self.customer)

            data = {
                'delivery_address': 'ул. Пушкина, 10',
                'items': [
                    {
                        'product': self.product.id,
                        'quantity': 2
                    }
                ]
            }

            # Ожидаем второй поток перед отправкой
            barrier.wait(timeout=5)

            # Отправляем запрос
            response = client.post(
                '/api/orders/',
                data,
                format='json',
                HTTP_IDEMPOTENCY_KEY='concurrent-test-123'
            )

            return response.status_code # возвращаем HTTP-статус для последующей проверки

        finally:
            # Освобождаем подключение этого потока
            close_old_connections()

    """ Проверка одновременного создания заказов с одинаковым ключом """
    def test_concurrent_orders_same_key(self):
        # Создаём барьер для двух потоков
        barrier = Barrier(2)

        # Запускаем два запроса
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self.send_order, barrier)
                for _ in range(2)
            ]

            # Получаем результаты обоих запросов
            statuses = [
                future.result()
                for future in futures
            ]

        # Проверяем HTTP-ответы
        self.assertEqual(sorted(statuses), [200, 201])

        # Проверяем, что создан только один заказ
        self.assertEqual(
            Order.objects.filter(
                customer=self.customer,
                idempotency_key='concurrent-test-123'
            ).count(),
            1
        )

    """ Проверка состояния гонки при создании заказов """
    def test_race_condition_same_key(self):
        """Оба запроса проверяют ключ до создания заказа."""

        # Барьер перед отправкой запросов
        start_barrier = Barrier(2)

        # Барьер после поиска существующего заказа
        find_barrier = Barrier(2)

        # Сохраняем настоящий метод поиска
        original_find = OrderViewSet.find_order_by_key

        def synchronized_find(view, key):
            # Реально обращаемся к PostgreSQL
            result = original_find(view, key)

            # Если заказ не найден, ждём второй поток
            if result is None:
                find_barrier.wait(timeout=10)

            return result

        # Временно добавляем синхронизацию в поиск
        with patch.object(
                OrderViewSet,
                'find_order_by_key',
                synchronized_find
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(self.send_order, start_barrier)
                    for _ in range(2)
                ]

                statuses = [
                    future.result()
                    for future in futures
                ]

        # Один запрос создаёт заказ, второй получает существующий
        self.assertEqual(sorted(statuses), [200, 201])

        # В базе должен находиться ровно один заказ
        self.assertEqual(
            Order.objects.filter(
                customer=self.customer,
                idempotency_key='concurrent-test-123'
            ).count(),
            1
        )
