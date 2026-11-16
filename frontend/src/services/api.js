// Получаем список доступных блюд из Django
// export позволяет использовать функцию в других файлах
// async означает, что функция может выполнять асинхронные операции
export async function getProducts() {
  // Vite Proxy перенаправит запрос на Django
  const response = await fetch('/api/menu/products/')

  // Проверяем, успешно ли Django обработал запрос
  if (!response.ok) {
    throw new Error('Не удалось загрузить меню')
  }

  // Преобразуем JSON-ответ в JavaScript-массив
  return await response.json()
}

// Отправляем логин и пароль пользователя в Django
export async function loginUser(username, password) {
  // Отправляем POST-запрос на сервер
  const response = await fetch('/api/auth/login/', {
    method: 'POST',

    // Сообщаем Django, что отправляем JSON
    headers: {
      'Content-Type': 'application/json',
    },

    // Превращаем JavaScript-объект в JSON-строку
    body: JSON.stringify({
      username: username,
      password: password,
    }),
  })

  // Если Django вернул ошибку авторизации
  if (!response.ok) {
    throw new Error('Не удалось войти в аккаунт')
  }

  // Возвращаем ответ Django
  return await response.json()
}

// Получаем профиль авторизованного пользователя
export async function getProfile(accessToken) {
  // Отправляем GET-запрос в Django
  const response = await fetch('/api/auth/me/', {
    method: 'GET',

    headers: {
      // Передаём Access Token в заголовке Authorization
      Authorization: `Bearer ${accessToken}`,
    },
  })

  // Проверяем, успешно ли обработан запрос
  if (!response.ok) {
    throw new Error('Не удалось получить профиль пользователя')
  }

  // Преобразуем JSON-ответ Django в объект JavaScript
  return await response.json()
}

// Отправляем запрос на выход из аккаунта
export async function logoutUser(accessToken, refreshToken) {
  // Обращаемся к Django
  const response = await fetch('/api/auth/logout/', {
    method: 'POST',

    headers: {
      // Django проверяет, кто отправляет запрос
      Authorization: `Bearer ${accessToken}`,

      // Указываем формат отправляемых данных
      'Content-Type': 'application/json',
    },

    // Отправляем refresh-токен для отзыва
    body: JSON.stringify({
      refresh: refreshToken,
    }),
  })

  // Проверяем результат запроса
  if (!response.ok) {
    throw new Error('Не удалось выполнить выход из аккаунта')
  }

  // Возвращаем ответ Django
  return await response.json()
}

// Отправляем данные нового пользователя в Django
export async function registerUser(userData) {
  // Отправляем POST-запрос на регистрацию
  const response = await fetch('/api/auth/register/', {
    method: 'POST',

    // Сообщаем серверу, что передаём JSON
    headers: {
      'Content-Type': 'application/json',
    },

    // Превращаем объект JavaScript в JSON-строку
    body: JSON.stringify(userData),
  })

  // Преобразуем JSON-ответ Django в объект JavaScript
  const data = await response.json()

  // Если Django отклонил регистрацию
  if (!response.ok) {
    // Превращаем объект ошибок Django в массив сообщений
    const messages = Object.entries(data).flatMap(([field, errors]) => {
      // Если значение является массивом, оставляем все его ошибки
      // Если нет — превращаем значение в массив из одного элемента
      const errorList = Array.isArray(errors) ? errors : [errors]

      // Добавляем к каждой ошибке название поля
      return errorList.map((error) => `${field}: ${error}`)
    })

    // Объединяем ошибки в одну строку через точку с запятой
    const message = messages.join('; ') || 'Не удалось зарегистрироваться'

    // Создаём ошибку с понятным текстом
    const error = new Error(message)

    // Дополнительно сохраняем ответ Django с ошибками полей
    error.fields = data

    // Передаём ошибку компоненту RegisterForm
    throw error
  }

  // Возвращаем данные зарегистрированного пользователя
  return data
}
