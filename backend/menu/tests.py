from django.test import TestCase
from rest_framework.test import APIClient
from users.models import User
from .models import Category, Product
from decimal import Decimal
from django.db import IntegrityError, transaction

""" Тесты на права разных пользователей приложения """
class MenuPermissionTests(TestCase):
    """Проверяем права пользователей при работе с меню."""

    def setUp(self):
        # Создаём покупателя
        self.customer = User.objects.create_user(
            username='menu_customer',
            email='menu_customer@example.com',
            password='testpass123',
            role='CUSTOMER'
        )
        # Создаём администратора ресторана
        self.admin_user = User.objects.create_user(
            username='menu_admin',
            email='menu_admin@example.com',
            password='testpass123',
            role='ADMIN'
        )
        # Создаём повара
        self.cook = User.objects.create_user(
            username='menu_cook',
            email='menu_cook@example.com',
            password='testpass123',
            role='COOK'
        )

        # Клиент для отправки запросов к API
        self.client = APIClient()

    """ Тест на запрет покупателю создавать категории """
    def test_customer_cannot_create_category(self):
        """Покупатель не может создавать категории блюд."""

        # Авторизуем покупателя
        self.client.force_authenticate(user=self.customer)

        # Покупатель пытается создать категорию
        response = self.client.post(
            '/api/menu/categories/',
            {
                'name': 'Пицца',
                'description': 'Итальянская пицца',
                'is_active': True
            },
            format='json'
        )

        # Ожидаем отказ в доступе
        self.assertEqual(response.status_code, 403)

    """ Тест на проверу создания категории админом и появление ее в БД """
    def test_admin_can_create_category(self):
        """Администратор может создавать категории блюд."""

        # Авторизуем администратора
        self.client.force_authenticate(user=self.admin_user)

        # Создаём категорию через API
        response = self.client.post(
            '/api/menu/categories/',
            {
                'name': 'Пицца',
                'description': 'Итальянская пицца',
                'is_active': True
            },
            format='json'
        )

        # Проверяем успешное создание
        self.assertEqual(response.status_code, 201)

        # Проверяем, что категория действительно появилась в базе
        self.assertTrue(
            Category.objects.filter(name='Пицца').exists()
        )


    """ Тест на проверку создания категории поваром и появление ее в БД """
    def test_cook_can_create_category(self):
        """Повар может создавать категории блюд."""

        # Авторизуем повара
        self.client.force_authenticate(user=self.cook)

        # Повар создаёт новую категорию
        response = self.client.post(
            '/api/menu/categories/',
            {
                'name': 'Супы',
                'description': 'Горячие первые блюда',
                'is_active': True
            },
            format='json'
        )

        # Сервер должен подтвердить создание
        self.assertEqual(response.status_code, 201)

        # Проверяем, что категория сохранилась в базе
        self.assertTrue(
            Category.objects.filter(name='Супы').exists()
        )

    """ Тест на возможность админу просматривать скрытую категорию """
    def test_admin_can_view_inactive_category(self):
        """Администратор может просматривать скрытую категорию."""

        # Создаём временно отключённую категорию
        category = Category.objects.create(
            name='Пицца',
            description='Итальянская кухня',
            is_active=False
        )

        # Авторизуем администратора
        self.client.force_authenticate(user=self.admin_user)

        # Пытаемся открыть скрытую категорию
        response = self.client.get(
            f'/api/menu/categories/{category.id}/'
        )

        # Администратор должен иметь доступ
        self.assertEqual(response.status_code, 200)

        # Проверяем, что получили правильную категорию
        self.assertEqual(response.data['id'], category.id)


    """ Тест на запрет покупателю просматривать не активную категорию """
    def test_customer_cannot_view_inactive_category(self):
        """Покупатель не видит неактивную категорию."""

        # Создаём скрытую категорию
        category = Category.objects.create(
            name='Временно недоступные блюда',
            description='Скрытая категория',
            is_active=False
        )

        # Авторизуем покупателя
        self.client.force_authenticate(user=self.customer)

        # Покупатель пытается открыть скрытую категорию
        response = self.client.get(
            f'/api/menu/categories/{category.id}/'
        )

        # Категория должна быть недоступна
        self.assertEqual(response.status_code, 404)

    """ Тест на запрет покупателю видеть список всех категорий """
    def test_customer_sees_only_active_categories(self):
        """Покупатель видит в списке только активные категории."""

        # Создаём две категории
        active_category = Category.objects.create(
            name='Пицца',
            is_active=True
        )

        inactive_category = Category.objects.create(
            name='Скрытые блюда',
            is_active=False
        )

        # Авторизуем покупателя
        self.client.force_authenticate(user=self.customer)

        # Получаем общий список категорий
        response = self.client.get('/api/menu/categories/')

        # Запрос должен выполниться успешно
        self.assertEqual(response.status_code, 200)

        # Получаем идентификаторы категорий из ответа
        category_ids = [category['id'] for category in response.data] # генератор списка (List Comprehension).

        # Активная категория присутствует
        self.assertIn(active_category.id, category_ids) # проверяет, что элемент есть в коллекции

        # Скрытая категория отсутствует
        self.assertNotIn(inactive_category.id, category_ids) # проверяет, что элемент нет в коллекции


    """ Тест на возможность админу просматривать скрытое блюдо """
    def test_admin_can_view_inactive_product(self):
        """Администратор может просматривать скрытое блюдо."""

        # Создаём категорию
        category = Category.objects.create(
            name='Пицца',
            is_active=True
        )

        # Создаём временно скрытое блюдо
        product = Product.objects.create(
            category=category,
            name='Маргарита',
            price='650.00',
            quantity=10,
            is_active=False
        )

        # Авторизуем администратора
        self.client.force_authenticate(user=self.admin_user)

        # Пытаемся получить скрытое блюдо по ID
        response = self.client.get(
            f'/api/menu/products/{product.id}/'
        )

        # Администратор должен видеть скрытое блюдо
        self.assertEqual(response.status_code, 200)

        # Проверяем, что получили нужный продукт
        self.assertEqual(response.data['id'], product.id)


    """ Тест на запрет покупателю видеть список всех блюд """
    def test_customer_cannot_view_inactive_product(self):
        """Покупатель не может просматривать скрытое блюдо."""

        # Создаём активную категорию
        category = Category.objects.create(
            name='Пицца',
            is_active=True
        )

        # Создаём скрытое блюдо
        product = Product.objects.create(
            category=category,
            name='Маргарита',
            price='650.00',
            quantity=10,
            is_active=False
        )

        # Авторизуем покупателя
        self.client.force_authenticate(user=self.customer)

        # Пытаемся открыть скрытое блюдо по ID
        response = self.client.get(
            f'/api/menu/products/{product.id}/'
        )

        # Покупателю блюдо должно быть недоступно
        self.assertEqual(response.status_code, 404)


    """ Тест на запрет покупателю видеть список всех блюд """
    def test_customer_sees_only_active_products(self):
        """Покупатель видит в списке только активные блюда."""

        # Создаём категорию
        category = Category.objects.create(
            name='Пицца',
            is_active=True
        )

        # Создаём доступное блюдо
        active_product = Product.objects.create(
            category=category,
            name='Маргарита',
            price='650.00',
            quantity=10,
            is_active=True
        )

        # Создаём скрытое блюдо
        inactive_product = Product.objects.create(
            category=category,
            name='Пепперони',
            price='750.00',
            quantity=10,
            is_active=False
        )

        # Авторизуем покупателя
        self.client.force_authenticate(user=self.customer)

        # Получаем список блюд
        response = self.client.get('/api/menu/products/')

        self.assertEqual(response.status_code, 200)

        # Извлекаем ID блюд из ответа
        product_ids = [product['id'] for product in response.data]

        # Доступное блюдо присутствует
        self.assertIn(active_product.id, product_ids)

        # Скрытого блюда нет
        self.assertNotIn(inactive_product.id, product_ids)


    """ Тест на возможность админа создавать блюда """
    def test_admin_can_create_product(self):
        """Администратор может добавлять новые блюда."""

        # Создаём категорию для нашего блюда
        category = Category.objects.create(
            name='Пицца',
            is_active=True
        )

        # Авторизуем администратора
        self.client.force_authenticate(user=self.admin_user)

        # Отправляем запрос на создание блюда
        response = self.client.post(
            '/api/menu/products/',
            {
                'category': category.id,
                'name': 'Пицца Маргарита',
                'description': 'Сыр, томаты и базилик',
                'price': '650.00',
                'weight': 450,
                'unit': 'гр.',
                'quantity': 10,
                'is_active': True
            },
            format='json'
        )

        # Проверяем успешное создание
        self.assertEqual(response.status_code, 201, response.data)

        # Проверяем, что блюдо действительно сохранилось
        product = Product.objects.get(name='Пицца Маргарита')

        self.assertEqual(product.category_id, category.id)
        self.assertEqual(product.price, Decimal('650.00'))
        self.assertEqual(product.quantity, 10)


    """ Тест на запрет покупателю создавать блюда """
    def test_customer_cannot_create_product(self):
        """Покупатель не может добавлять блюда в меню."""

        # Создаём категорию
        category = Category.objects.create(
            name='Пицца',
            is_active=True
        )

        # Авторизуем покупателя
        self.client.force_authenticate(user=self.customer)

        # Покупатель пытается создать блюдо
        response = self.client.post(
            '/api/menu/products/',
            {
                'category': category.id,
                'name': 'Бесплатная пицца',
                'price': '0.00',
                'quantity': 100,
                'is_active': True
            },
            format='json'
        )

        # Покупателю запрещено создавать блюда
        self.assertEqual(response.status_code, 403)

        # Проверяем, что блюдо не появилось в базе
        self.assertFalse(
            Product.objects.filter(name='Бесплатная пицца').exists()
        )


    """ Тест на возможность админу менять цену блюда """
    def test_admin_can_update_product_price(self):
        """Администратор может изменять цену блюда."""

        # Создаём категорию
        category = Category.objects.create(
            name='Пицца',
            is_active=True
        )

        # Создаём блюдо с первоначальной ценой
        product = Product.objects.create(
            category=category,
            name='Маргарита',
            price=Decimal('650.00'),
            quantity=10,
            is_active=True
        )

        # Авторизуем администратора
        self.client.force_authenticate(user=self.admin_user)

        # Изменяем только цену блюда (putch частично меняет объект)
        response = self.client.patch(
            f'/api/menu/products/{product.id}/',
            {'price': '750.00'},
            format='json'
        )

        # Проверяем успешное изменение
        self.assertEqual(response.status_code, 200, response.data)

        # Загружаем актуальные данные из базы
        product.refresh_from_db()

        # Проверяем новую цену
        self.assertEqual(product.price, Decimal('750.00'))

        # Название и остаток не должны измениться
        self.assertEqual(product.name, 'Маргарита')
        self.assertEqual(product.quantity, 10)


    """ Тест на запрет покупателю менять цену блюда """
    def test_customer_cannot_update_product_price(self):
        """Покупатель не может самостоятельно менять цену блюда."""

        # Создаём категорию
        category = Category.objects.create(
            name='Пицца',
            is_active=True
        )

        # Создаём блюдо
        product = Product.objects.create(
            category=category,
            name='Маргарита',
            price=Decimal('650.00'),
            quantity=10,
            is_active=True
        )

        # Авторизуем покупателя
        self.client.force_authenticate(user=self.customer)

        # Покупатель пытается изменить цену
        response = self.client.patch(
            f'/api/menu/products/{product.id}/',
            {'price': '1.00'},
            format='json'
        )

        # Сервер должен запретить редактирование
        self.assertEqual(response.status_code, 403)

        # Получаем актуальные данные из базы
        product.refresh_from_db()

        # Цена должна остаться прежней
        self.assertEqual(product.price, Decimal('650.00'))


    """ Тест на восстановления скрытого блюда поваром 
        и получение доступа к нему покупателям """
    def test_cook_can_reactivate_product(self):
        """Повар может вернуть скрытое блюдо в меню."""

        # Создаём категорию
        category = Category.objects.create(
            name='Пицца',
            is_active=True
        )

        # Создаём скрытое блюдо
        product = Product.objects.create(
            category=category,
            name='Маргарита',
            price=Decimal('650.00'),
            quantity=10,
            is_active=False
        )

        # Авторизуем повара
        self.client.force_authenticate(user=self.cook)

        # Возвращаем блюдо в продажу
        response = self.client.patch(
            f'/api/menu/products/{product.id}/',
            {'is_active': True},
            format='json'
        )

        # Проверяем успешное изменение
        self.assertEqual(response.status_code, 200, response.data)

        # Загружаем актуальное состояние из базы
        product.refresh_from_db()

        # Блюдо снова активно
        self.assertTrue(product.is_active)

        # Проверяем, что покупатель теперь видит блюдо
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(
            f'/api/menu/products/{product.id}/'
        )

        self.assertEqual(response.status_code, 200)


    """ Тест на отрицательную цену """
    def test_cannot_create_product_with_negative_price(self):
        """Нельзя создать блюдо с отрицательной ценой."""

        # Создаём категорию
        category = Category.objects.create(
            name='Пицца',
            is_active=True
        )

        # Авторизуем администратора
        self.client.force_authenticate(user=self.admin_user)

        # Пытаемся создать блюдо с отрицательной ценой
        response = self.client.post(
            '/api/menu/products/',
            {
                'category': category.id,
                'name': 'Маргарита',
                'price': '-500.00',
                'quantity': 10,
                'is_active': True
            },
            format='json'
        )

        # Сервер должен отклонить некорректную цену
        self.assertEqual(response.status_code, 400, response.data)

        # Блюдо не должно сохраниться в базе
        self.assertFalse(
            Product.objects.filter(name='Маргарита').exists()
        )


    """ Тест на запрет отрецательной цены даже с использованием SQL-запроса """
    def test_database_rejects_negative_product_price(self):
        """PostgreSQL запрещает отрицательную цену блюда."""

        # Создаём категорию
        category = Category.objects.create(
            name='Пицца',
            is_active=True
        )

        # Ожидаем, что база данных отклонит отрицательную цену
        with self.assertRaises(IntegrityError):
            with transaction.atomic(): # Вложенный transaction.atomic() создаёт точку сохранения (savepoint).
                Product.objects.create(
                    category=category,
                    name='Маргарита',
                    price=Decimal('-500.00'),
                    quantity=10,
                    is_active=True
                )

        # Убеждаемся, что некорректное блюдо не сохранилось
        self.assertFalse(
            Product.objects.filter(name='Маргарита').exists()
        )

    """ Тест на запрет покупателю видеть блюдо из отключенной категории """
    def test_customer_cannot_view_product_from_inactive_category(self):
        """Покупатель не видит блюдо из отключённой категории."""

        # Создаём скрытую категорию
        category = Category.objects.create(
            name='Пицца',
            is_active=False
        )

        # Само блюдо остаётся активным
        product = Product.objects.create(
            category=category,
            name='Маргарита',
            price=Decimal('650.00'),
            quantity=10,
            is_active=True
        )

        # Авторизуем покупателя
        self.client.force_authenticate(user=self.customer)

        # Получаем список блюд
        response = self.client.get('/api/menu/products/')

        self.assertEqual(response.status_code, 200)

        # Получаем ID блюд из ответа
        product_ids = [item['id'] for item in response.data]

        # Блюдо из скрытой категории не должно отображаться
        self.assertNotIn(product.id, product_ids)