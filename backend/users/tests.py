from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


class UserRegistrationTests(TestCase):
    def setUp(self):
        # Создаём клиент для отправки HTTP-запросов
        self.client = APIClient()

    """ Тест на запрет пользователю назначить себе роль ADMIN """
    def test_registration_cannot_assign_admin_role(self):
        """Пользователь не может назначить себе роль ADMIN."""

        # Пытаемся зарегистрироваться администратором
        response = self.client.post(
            '/api/auth/register/',
            {
                'username': 'new_customer',
                'email': 'new_customer@example.com',
                'password': 'SecurePass123!',
                'password_confirm': 'SecurePass123!',
                'first_name': 'Иван',
                'last_name': 'Иванов',
                'role': 'ADMIN'
            },
            format='json'
        )

        # Регистрация должна пройти успешно.
        # При ошибки показывает фактический HTTP-код
        self.assertEqual(response.status_code, 201)

        # Получаем зарегистрированного пользователя
        user = User.objects.get(username='new_customer')

        # Несмотря на запрос ADMIN, роль должна быть CUSTOMER
        self.assertEqual(user.role, User.Role.CUSTOMER)

        # Проверяем, что пользователь не стал суперпользователем
        self.assertFalse(user.is_superuser)

    """ Тест на невозможность хранение пароля в БД открытым текстом """
    def test_registration_password_is_hashed(self):
        """Пароль нового пользователя хранится в виде хеша."""

        # Регистрируем нового покупателя
        response = self.client.post(
            '/api/auth/register/',
            {
                'username': 'secure_customer',
                'email': 'secure_customer@example.com',
                'password': 'SecurePass123!',
                'password_confirm': 'SecurePass123!',
                'first_name': 'Иван',
                'last_name': 'Иванов'
            },
            format='json'
        )

        # Убеждаемся, что регистрация прошла успешно
        self.assertEqual(response.status_code, 201)

        # Получаем созданного пользователя из базы
        user = User.objects.get(username='secure_customer')

        # Пароль не должен храниться открытым текстом
        self.assertNotEqual(user.password, 'SecurePass123!')

        # При входе Django проверяет пароль с помощью check_password(),
        # а не сравнивает две обычные строки.
        self.assertTrue(user.check_password('SecurePass123!'))


    """ Тест на получение двух токкенов после регистрации пользователя """
    def test_user_can_login_and_receive_jwt_tokens(self):
        """Покупатель может войти и получить JWT-токены."""

        # Создаём пользователя с правильно хешированным паролем
        User.objects.create_user(
            username='login_customer',
            email='login_customer@example.com',
            password='SecurePass123!',
            role=User.Role.CUSTOMER
        )

        # Отправляем логин и пароль
        response = self.client.post(
            '/api/auth/login/',
            {
                'username': 'login_customer',
                'password': 'SecurePass123!'
            },
            format='json'
        )

        # Успешная авторизация
        self.assertEqual(response.status_code, 200, response.data)

        # Сервер должен вернуть оба JWT-токена
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

        # Токены не должны быть пустыми
        self.assertTrue(response.data['access'])
        self.assertTrue(response.data['refresh'])

    """ Тест, чтоб убедиться, что /api/auth/me/ возвращает данные именно того пользователя, которому принадлежит access-токен. """
    def test_user_can_get_profile_with_jwt(self):
        """Пользователь получает свой профиль через JWT."""

        # Создаём покупателя
        User.objects.create_user(
            username='profile_customer',
            email='profile@example.com',
            password='SecurePass123!',
            first_name='Иван',
            last_name='Иванов',
            role=User.Role.CUSTOMER
        )

        # Входим в систему и получаем JWT
        login_response = self.client.post(
            '/api/auth/login/',
            {
                'username': 'profile_customer',
                'password': 'SecurePass123!'
            },
            format='json'
        )

        self.assertEqual(login_response.status_code, 200)

        access_token = login_response.data['access']

        # Передаём access-токен в заголовке Authorization
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {access_token}'
        )

        # Запрашиваем профиль пользователя
        response = self.client.get('/api/auth/me/')

        self.assertEqual(response.status_code, 200, response.data)

        # Проверяем, чьи именно данные вернулись
        self.assertEqual(response.data['username'], 'profile_customer')
        self.assertEqual(response.data['email'], 'profile@example.com')
        self.assertEqual(response.data['role'], 'CUSTOMER')

    """ Тест на возможность покупателю вносить разрешенные изменения """
    def test_user_can_update_own_profile(self):
        """Покупатель может изменить свой телефон."""

        # Создаём покупателя
        user = User.objects.create_user(
            username='profile_edit',
            email='profile_edit@example.com',
            password='SecurePass123!',
            first_name='Иван',
            last_name='Иванов',
            role=User.Role.CUSTOMER
        )

        # Авторизуем пользователя для теста
        self.client.force_authenticate(user=user)

        # Изменяем телефон через API
        response = self.client.patch(
            '/api/auth/me/',
            {'phone': '+79991234567'},
            format='json'
        )

        # Сервер должен успешно обработать запрос
        self.assertEqual(response.status_code, 200, response.data)

        # Перечитываем данные из базы
        user.refresh_from_db()

        # Проверяем сохранённый телефон
        self.assertEqual(user.phone, '+79991234567')


    """ Тест на защиту изменить покупателю свою роль при редактировании профиля """
    def test_user_cannot_change_own_role(self):
        """Покупатель не может изменить свою роль через профиль."""

        # Создаём покупателя
        user = User.objects.create_user(
            username='role_customer',
            email='role_customer@example.com',
            password='SecurePass123!',
            role=User.Role.CUSTOMER
        )

        # Авторизуем покупателя
        self.client.force_authenticate(user=user)

        # Пытаемся изменить роль и имя одновременно
        response = self.client.patch(
            '/api/auth/me/',
            {
                'first_name': 'Пётр Первый',
                'role': 'ADMIN'
            },
            format='json'
        )

        # Запрос обрабатывается, но роль менять нельзя
        self.assertEqual(response.status_code, 200, response.data)

        # Получаем актуальные данные из БД
        user.refresh_from_db()

        # Разрешённое поле изменилось
        self.assertEqual(user.first_name, 'Пётр Первый')

        # Запрещённое поле осталось прежним
        self.assertEqual(user.role, User.Role.CUSTOMER)

        # Дополнительно проверяем права суперпользователя
        self.assertFalse(user.is_superuser)

    """ Тест на автополучение нового access-токена """
    def test_user_can_refresh_access_token(self):
        """Пользователь может обновить access-токен."""

        # Создаём покупателя
        User.objects.create_user(
            username='refresh_customer',
            email='refresh@example.com',
            password='SecurePass123!',
            role=User.Role.CUSTOMER
        )

        # Входим в аккаунт
        login_response = self.client.post(
            '/api/auth/login/',
            {
                'username': 'refresh_customer',
                'password': 'SecurePass123!'
            },
            format='json'
        )

        # Проверяем успешный вход
        self.assertEqual(login_response.status_code, 200)

        # Получаем refresh-токен
        refresh_token = login_response.data['refresh']

        # Запрашиваем новый access-токен
        response = self.client.post(
            '/api/auth/refresh/',
            {
                'refresh': refresh_token
            },
            format='json'
        )

        # Проверяем успешное обновление
        self.assertEqual(response.status_code, 200, response.data)

        # Сервер должен вернуть не пустой access-токен
        self.assertIn('access', response.data)
        self.assertTrue(response.data['access'])


        """ Тест на добавление refresh-токен в чёрный список (blacklist) после выхода из аккаунта """
        def test_logout_revokes_refresh_token(self):
            """После выхода refresh-токен нельзя использовать повторно."""

            # Создаём покупателя
            User.objects.create_user(
                username='logout_customer',
                email='logout@example.com',
                password='SecurePass123!',
                role=User.Role.CUSTOMER
            )

            # Входим в аккаунт
            login_response = self.client.post(
                '/api/auth/login/',
                {
                    'username': 'logout_customer',
                    'password': 'SecurePass123!'
                },
                format='json'
            )

            self.assertEqual(login_response.status_code, 200)

            # Сохраняем оба токена
            access_token = login_response.data['access']
            refresh_token = login_response.data['refresh']

            # Авторизуем запрос на выход
            self.client.credentials(
                HTTP_AUTHORIZATION=f'Bearer {access_token}'
            )

            # Выходим из аккаунта
            logout_response = self.client.post(
                '/api/auth/logout/',
                {'refresh': refresh_token},
                format='json'
            )

            # Выход должен пройти успешно
            self.assertEqual(
                logout_response.status_code,
                200,
                getattr(logout_response, 'data', None)
            )

            # Убираем заголовок авторизации
            self.client.credentials()

            # Пробуем обновить токен после выхода
            refresh_response = self.client.post(
                '/api/auth/refresh/',
                {'refresh': refresh_token},
                format='json'
            )

            # Отозванный refresh-токен использовать нельзя
            self.assertEqual(refresh_response.status_code, 401)