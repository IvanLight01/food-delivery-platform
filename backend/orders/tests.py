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

    """ Запрет на заказ блюда, если установлен is_active=False,
        при этом блюда в наличии есть. """
    def test_customer_cannot_order_inactive_product(self):
        """Покупатель не должен заказывать неактивное блюдо."""

        # Создаём категорию
        category = Category.objects.create(
            name='Основные блюда'
        )

        # Создаём блюдо, которое недоступно для заказа
        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            quantity=10,
            is_active=False
        )

        # Авторизуем покупателя
        self.client.force_authenticate(user=self.customer)

        # Запоминаем количество заказов
        count_before = Order.objects.count()

        # Пытаемся заказать неактивное блюдо
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
            HTTP_IDEMPOTENCY_KEY='inactive-product-test-123'
        )

        # Сервер должен отклонить заказ
        self.assertEqual(response.status_code, 400)

        # Проверяем, что сервер отклонил именно неактивное блюдо
        self.assertIn(
            'недоступно для заказа',
            str(response.data['items'])
        )

        # В базе не должно появиться нового заказа
        self.assertEqual(
            Order.objects.count(),
            count_before
        )

    """ Завпрет на заказ больше чем установленно в quantity.
        И не допустимость создания заказа. """
    def test_customer_cannot_order_more_than_available(self):
        """Нельзя заказать больше порций, чем есть в наличии."""

        category = Category.objects.create(name='Основные блюда')

        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            quantity=3,
            is_active=True
        )

        self.client.force_authenticate(user=self.customer)

        count_before = Order.objects.count()

        response = self.client.post(
            '/api/orders/',
            {
                'delivery_address': 'ул. Пушкина, 10',
                'items': [
                    {'product': product.id, 'quantity': 5}
                ]
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY='stock-test-123'
        )

        # Ожидаем отказ
        self.assertEqual(response.status_code, 400)

        # Заказ не должен создаваться
        self.assertEqual(Order.objects.count(), count_before)


    """ Проверка списания остатков """
    def test_order_creation_decreases_product_stock(self):
        """После создания заказа остаток блюда уменьшается."""

        # Создаём категорию
        category = Category.objects.create(
            name='Основные блюда'
        )

        # Создаём блюдо с остатком 10 порций
        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            quantity=10,
            is_active=True
        )

        # Авторизуем покупателя
        self.client.force_authenticate(user=self.customer)

        # Создаём заказ на 3 порции
        response = self.client.post(
            '/api/orders/',
            {
                'delivery_address': 'ул. Пушкина, 10',
                'items': [
                    {
                        'product': product.id,
                        'quantity': 3
                    }
                ]
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY='stock-decrease-test-123'
        )

        # Заказ должен успешно создаться
        self.assertEqual(response.status_code, 201)

        # Получаем обновлённый остаток из PostgreSQL
        # Метод, который заново загружает данные блюда
        # Объект product может содержать старое значение в памяти Python, если не использовать этот метод
        product.refresh_from_db()

        # Было 10, заказали 3, должно остаться 7
        self.assertEqual(product.quantity, 7)

    """ Суммарное списание одинаковых блюд """
    def test_duplicate_product_items_decrease_stock_correctly(self):
        """Одинаковые блюда в заказе должны суммироваться при списании."""

        category = Category.objects.create(
            name='Основные блюда'
        )

        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            quantity=10,
            is_active=True
        )

        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            '/api/orders/',
            {
                'delivery_address': 'ул. Пушкина, 10',
                'items': [
                    {'product': product.id, 'quantity': 4},
                    {'product': product.id, 'quantity': 3}
                ]
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY='duplicate-stock-test-123'
        )

        # Заказ успешно создаётся
        self.assertEqual(response.status_code, 201)

        # Загружаем обновлённое количество из PostgreSQL
        product.refresh_from_db()

        # Должно остаться 10 - (4 + 3) = 3
        self.assertEqual(product.quantity, 3)

    """ Защита от повторного списания блюд """
    def test_repeated_order_does_not_decrease_stock_twice(self):
        """Повторный запрос не должен списывать остаток дважды."""

        # Создаём категорию и блюдо с запасом 10 порций
        category = Category.objects.create(
            name='Основные блюда'
        )

        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            quantity=10,
            is_active=True
        )

        # Авторизуем покупателя
        self.client.force_authenticate(user=self.customer)

        data = {
            'delivery_address': 'ул. Пушкина, 10',
            'items': [
                {
                    'product': product.id,
                    'quantity': 3
                }
            ]
        }

        # Первый запрос создаёт заказ
        response1 = self.client.post(
            '/api/orders/',
            data,
            format='json',
            HTTP_IDEMPOTENCY_KEY='repeat-stock-test-123'
        )

        self.assertEqual(response1.status_code, 201)

        product.refresh_from_db()
        self.assertEqual(product.quantity, 7)

        # Повторяем тот же запрос с тем же ключом
        response2 = self.client.post(
            '/api/orders/',
            data,
            format='json',
            HTTP_IDEMPOTENCY_KEY='repeat-stock-test-123'
        )

        # Сервер возвращает уже созданный заказ
        self.assertEqual(response2.status_code, 200)

        # ID заказов должны совпадать
        self.assertEqual(
            response1.data['id'],
            response2.data['id']
        )

        # Проверяем, что порции не списались повторно
        product.refresh_from_db()
        self.assertEqual(product.quantity, 7)

        # В базе должен быть только один заказ
        self.assertEqual(
            Order.objects.filter(
                customer=self.customer,
                idempotency_key='repeat-stock-test-123'
            ).count(),
            1
        )


    """ Отмена заказа восстанавливает остаток продукта на складе """
    def test_cancelling_order_restores_product_stock(self):
        """Отмена нового заказа возвращает списанные порции."""

        # Создаём категорию и блюдо
        category = Category.objects.create(
            name='Основные блюда'
        )

        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            quantity=10,
            is_active=True
        )

        # Покупатель оформляет заказ
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            '/api/orders/',
            {
                'delivery_address': 'ул. Пушкина, 10',
                'items': [
                    {'product': product.id, 'quantity': 3}
                ]
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY='cancel-stock-test-123'
        )

        self.assertEqual(response.status_code, 201)

        order_id = response.data['id']

        # Проверяем списание: 10 - 3 = 7
        product.refresh_from_db()
        self.assertEqual(product.quantity, 7)

        # Для смены статуса используем администратора
        self.client.force_authenticate(user=self.cook)

        # Отменяем заказ
        response = self.client.post(
            f'/api/orders/{order_id}/change_status/',
            {'status': 'CANCELLED'},
            format='json'
        )

        # Проверяем успешную отмену
        self.assertEqual(response.status_code, 200)

        # Получаем актуальные данные
        product.refresh_from_db()

        # Остаток должен восстановиться: 7 + 3 = 10
        self.assertEqual(product.quantity, 10)

        # Статус заказа должен быть CANCELLED
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, Order.Status.CANCELLED)

        # Повторно пытаемся отменить тот же заказ
        response2 = self.client.post(
            f'/api/orders/{order_id}/change_status/',
            {'status': 'CANCELLED'},
            format='json'
        )

        # Повторный переход запрещён
        self.assertEqual(response2.status_code, 400)

        # Остаток не должен увеличиться второй раз
        product.refresh_from_db()
        self.assertEqual(product.quantity, 10)


    """ Запрещает отменять заказ после статуса COOKING """
    def test_cannot_cancel_order_after_cooking_started(self):
        """Нельзя отменить заказ после начала приготовления."""

        category = Category.objects.create(
            name='Основные блюда'
        )

        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            quantity=10,
            is_active=True
        )

        # Покупатель создаёт заказ
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            '/api/orders/',
            {
                'delivery_address': 'ул. Пушкина, 10',
                'items': [
                    {'product': product.id, 'quantity': 3}
                ]
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY='cooking-cancel-test-123'
        )

        self.assertEqual(response.status_code, 201)
        order_id = response.data['id']

        # Повар меняет статус заказа
        self.client.force_authenticate(user=self.cook)

        for new_status in ['CONFIRMED', 'COOKING']:
            response = self.client.post(
                f'/api/orders/{order_id}/change_status/',
                {'status': new_status},
                format='json'
            )
            self.assertEqual(response.status_code, 200)

        # Пытаемся отменить уже готовящийся заказ
        response = self.client.post(
            f'/api/orders/{order_id}/change_status/',
            {'status': 'CANCELLED'},
            format='json'
        )

        # Отмена запрещена
        self.assertEqual(response.status_code, 400)

        # Статус должен остаться COOKING
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, Order.Status.COOKING)

        # Списанные порции не возвращаются
        product.refresh_from_db()
        self.assertEqual(product.quantity, 7)


    """ Возможность покупателю отменить свой собственный заказ """
    def test_customer_can_cancel_own_order(self):
        """Покупатель может отменить свой новый заказ."""

        # Создаём блюдо с остатком 10 порций
        category = Category.objects.create(
            name='Основные блюда'
        )

        product = Product.objects.create(
            category=category,
            name='Лазанья',
            price=Decimal('900.00'),
            quantity=10,
            is_active=True
        )

        # Авторизуем покупателя
        self.client.force_authenticate(user=self.customer)

        # Создаём заказ на 3 порции
        create_response = self.client.post(
            '/api/orders/',
            {
                'delivery_address': 'ул. Пушкина, 10',
                'items': [
                    {'product': product.id, 'quantity': 3}
                ]
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY='customer-cancel-test-123'
        )

        self.assertEqual(create_response.status_code, 201)
        order_id = create_response.data['id']

        # После создания заказа осталось 7 порций
        product.refresh_from_db()
        self.assertEqual(product.quantity, 7)

        # Покупатель отменяет собственный заказ
        cancel_response = self.client.post(
            f'/api/orders/{order_id}/cancel/',
            format='json'
        )

        # Отмена должна пройти успешно
        self.assertEqual(cancel_response.status_code, 200)

        # Статус заказа изменился
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, Order.Status.CANCELLED)

        # Остаток восстановился
        product.refresh_from_db()
        self.assertEqual(product.quantity, 10)

        # Покупатель повторно пытается отменить тот же заказ
        second_response = self.client.post(
            f'/api/orders/{order_id}/cancel/',
            format='json'
        )

        # Повторная отмена должна быть запрещена
        self.assertEqual(second_response.status_code, 400)

        # Проверяем, что статус остался CANCELLED
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

        # Продукты не должны возвращаться на склад второй раз
        product.refresh_from_db()
        self.assertEqual(product.quantity, 10)


    """ Покупатель не имеет право отменять и видеть заказ другого покупателя """
    def test_customer_cannot_cancel_another_customers_order(self):
        """Покупатель не может отменить чужой заказ."""

        # Создаём заказ, принадлежащий первому покупателю
        order = Order.objects.create(
            customer=self.customer,
            delivery_address='ул. Пушкина, 10',
            status=Order.Status.NEW,
        )

        # Используем отдельного покупателя для этого теста.
        # get_or_create не создаст дубликат username.
        other_customer, created = User.objects.get_or_create(
            username='other_customer',
            defaults={'role': 'CUSTOMER'}
        )

        # Второй покупатель пытается отменить чужой заказ
        self.client.force_authenticate(user=other_customer)

        response = self.client.post(
            f'/api/orders/{order.id}/cancel/',
            format='json'
        )

        # Чужой заказ недоступен
        self.assertEqual(response.status_code, 404)

        # Статус заказа не изменился
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)


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


    """ Отправка заказа в отдельном потоке """
    def send_stock_order(self, barrier, user, product_id, key):
        """Отправляет заказ из отдельного потока."""

        # У каждого потока собственное соединение с БД
        close_old_connections()

        try:
            # Создаём отдельный API-клиент
            client = APIClient()
            client.force_authenticate(user=user)

            data = {
                'delivery_address': 'ул. Пушкина, 10',
                'items': [
                    {
                        'product': product_id,
                        'quantity': 4
                    }
                ]
            }

            # Ждём, пока оба потока будут готовы
            barrier.wait(timeout=10)

            # Отправляем запрос с уникальным ключом
            response = client.post(
                '/api/orders/',
                data,
                format='json',
                HTTP_IDEMPOTENCY_KEY=key
            )

            return response.status_code

        finally:
            # Закрываем соединение этого потока
            close_old_connections()


    """ Защита от двойной продажи при параллельных зхаказах """
    def test_concurrent_orders_do_not_oversell_stock(self):
        """Два покупателя не могут купить больше доступного остатка."""

        # На складе всего 5 порций
        self.product.quantity = 5
        self.product.save(update_fields=['quantity'])

        # Создаём второго покупателя
        second_customer = User.objects.create_user(
            username='second_stock_customer',
            email='second_stock@test.example',
            password='TestPassword123!',
            role='CUSTOMER'
        )

        # Синхронизируем начало двух запросов
        barrier = Barrier(2)

        # Отправляем два заказа одновременно
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    self.send_stock_order,
                    barrier,
                    self.customer,
                    self.product.id,
                    'stock-customer-1'
                ),
                executor.submit(
                    self.send_stock_order,
                    barrier,
                    second_customer,
                    self.product.id,
                    'stock-customer-2'
                )
            ]

            # Получаем HTTP-статусы обоих запросов
            statuses = [future.result() for future in futures]

        # Один заказ успешный, второй отклонён
        self.assertEqual(sorted(statuses), [201, 400]) # используем sorted(), потому что не знаем заранее, какой покупатель успеет первым

        # Получаем актуальный остаток из PostgreSQL
        self.product.refresh_from_db()

        # 5 - 4 = 1
        self.assertEqual(self.product.quantity, 1)

        # В базе должен быть ровно один заказ
        self.assertEqual(Order.objects.count(), 1)

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
