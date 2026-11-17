import { useEffect, useState } from 'react'
import './App.css'
import ProductList from './components/ProductList'
import Cart from './components/Cart'
import LoginForm from './components/LoginForm'
import RegisterForm from './components/RegisterForm'
import {
  getProducts,
  loginUser,
  getProfile,
  logoutUser,
  registerUser,
  refreshAccessToken,
} from './services/api'
import useCart from './hooks/useCart'

function App() {
  // Список блюд, полученных от Django
  const [products, setProducts] = useState([])
  // Получаем корзину из пользовательского хука
  const { cart, setCart, handleAddToCart, handleDecreaseQuantity, syncCartWithProducts } = useCart()
  // Состояние загрузки
  const [loading, setLoading] = useState(true)
  // Сообщение об ошибке
  const [error, setError] = useState('')
  // Храним access-токен текущего пользователя
  // Пока только в памяти React, без localStorage
  const [accessToken, setAccessToken] = useState(null)
  // Refresh-токен потребуется для выхода из аккаунта
  const [refreshToken, setRefreshToken] = useState(null)
  // Данные авторизованного пользователя
  // null означает, что профиль пока не загружен
  const [profile, setProfile] = useState(null)
  // Сообщение об ошибке выхода из аккаунта
  const [logoutError, setLogoutError] = useState('')
  // Сообщение об ошибке загрузки профиля
  const [profileError, setProfileError] = useState('')
  // Какая форма сейчас открыта:
  // 'login' — вход, 'register' — регистрация
  const [authMode, setAuthMode] = useState('login')
  // Сообщение после успешной регистрации
  const [registrationMessage, setRegistrationMessage] = useState('')

  // Выполняется после успешного входа через LoginForm
  // Получаем токены от LoginForm и загружаем профиль
  async function handleLoginSuccess(tokens) {
    // Очищаем данные предыдущей попытки
    setProfile(null)

    // Сохраняем access-токен
    setAccessToken(tokens.access)
    // Сохраняем refresh-токен
    setRefreshToken(tokens.refresh)

    try {
      // Обращаемся к Django за данными пользователя
      // Передаём оба токена напрямую из ответа Django
      const userData = await getProfileWithRefresh(tokens.access, tokens.refresh)
      // Записываем профиль в состояние React
      setProfile(userData)
      // Пользователь вошёл — уведомление о регистрации больше не нужно
      setRegistrationMessage('')
    } catch (err) {
      // Сбрасываем авторизацию
      setAccessToken(null)
      setRefreshToken(null)

      // Передаём ошибку вызывающей функции в LoginForm.jsx
      throw err
    }
  }

  // Обновляем Access Token с помощью Refresh Token
  // Получаем Refresh Token через параметр функции
  async function handleRefreshToken(currentRefreshToken) {
    try {
      // Используем переданный токен, а не состояние текущего рендера
      const data = await refreshAccessToken(currentRefreshToken)

      // Сохраняем новый access-токен в состоянии React
      setAccessToken(data.access)

      // Возвращаем новый токен для дальнейшего использования
      return data.access
    } catch (err) {
      // Пока только сообщаем об ошибке в консоли
      console.error('Ошибка обновления токена:', err)

      // Передаём ошибку вызывающему коду
      throw err
    }
  }

  // Получаем профиль, при необходимости обновляя Access Token
  async function getProfileWithRefresh(token, currentRefreshToken) {
    try {
      // Сначала пробуем получить профиль с текущим токеном
      return await getProfile(token)
    } catch (err) {
      // Если ошибка не связана с авторизацией — передаём её дальше
      if (err.message !== 'ACCESS_TOKEN_INVALID') {
        throw err
      }

      // При ошибке 401 пробуем обновить Access Token
      // Передаём Refresh Token напрямую в функцию обновления
      const newAccessToken = await handleRefreshToken(currentRefreshToken)
      // Повторяем запрос профиля с новым токеном
      return await getProfile(newAccessToken)
    }
  }

  // Обрабатываем выход пользователя из аккаунта
  async function handleLogout() {
    // Убираем сообщение от предыдущей попытки
    setLogoutError('')

    try {
      // Просим Django отозвать refresh-токен
      await logoutUser(accessToken, refreshToken)

      // Удаляем токены из памяти React
      setAccessToken(null)
      setRefreshToken(null)

      // Очищаем данные пользователя
      setProfile(null)
    } catch (err) {
      // Если выход не удался, показываем ошибку
      setLogoutError(err.message)
    }
  }

  // Вызывается после успешной регистрации
  function handleRegisterSuccess() {
    // Показываем сообщение пользователю
    setRegistrationMessage('✅ Регистрация прошла успешно! Теперь войдите в аккаунт.')

    // Переключаем интерфейс на форму входа
    setAuthMode('login')
  }

  // Переключаем форму входа или регистрации
  // Здесь mode — параметр функции. Он принимает 'login' или 'register
  function handleAuthModeChange(mode) {
    // Запоминаем выбранную форму
    setAuthMode(mode)

    // Удаляем старое уведомление о регистрации
    setRegistrationMessage('')
  }

  useEffect(() => {
    // Получаем блюда после открытия страницы
    async function loadProducts() {
      try {
        // Загружаем блюда из Django
        const data = await getProducts()
        // Обновляем список блюд
        setProducts(data)
        // Проверяем корзину по актуальнымостаткам
        // проверка находится в useCart.js
        syncCartWithProducts(data)
      } catch (err) {
        // Заполняем ошибку
        setError(err.message)
      } finally {
        // Завершаем загрузку
        setLoading(false)
      }
    }
    // Вызываем функцию загрузки
    loadProducts()
  }, [])

  return (
    <div className="app">
      <header>
        <h1>🍕 Food Platform</h1>
        <p>Вкусная еда с доставкой на дом</p>
      </header>

      {/* Форма авторизации пользователя */}
      {/* Передаём дочернему компоненту функцию через props */}
      {/* Формы показываем, только если пользователь не вошёл */}
      {!profile && (
        <section>
          {/* Кнопки переключения между формами */}
          <button type="button" onClick={() => handleAuthModeChange('login')}>
            Вход
          </button>

          <button type="button" onClick={() => handleAuthModeChange('register')}>
            Регистрация
          </button>

          {/* Отображаем только выбранную форму */}
          {authMode === 'login' ? (
            <>
              {/* Сообщение отображается после успешной регистрации */}
              {registrationMessage && <p role="status">{registrationMessage}</p>}

              {/* Форма входа */}
              <LoginForm onLoginSuccess={handleLoginSuccess} />
            </>
          ) : (
            <RegisterForm onRegisterSuccess={handleRegisterSuccess} />
          )}
        </section>
      )}

      {/* Показываем информацию только после загрузки профиля */}
      {profile && (
        <div>
          <p>👤 Вы вошли как {profile.username}</p>

          {/* Кнопка выхода из аккаунта */}
          <button type="button" onClick={handleLogout}>
            Выйти
          </button>
        </div>
      )}

      {/* Показываем ошибку выхода, если она возникла */}
      {logoutError && <p role="alert">❌ {logoutError}</p>}

      <main>
        <h2>Наше меню({products.length})</h2>
        <p>🛒 Всего порций: {cart.reduce((total, item) => total + item.quantityInCart, 0)}</p>

        {loading && <p>Загружаем блюда...</p>}

        {error && <p>Ошибка: {error}</p>}

        {!loading && !error && products.length === 0 && <p>Пока нет доступных блюд.</p>}

        <ProductList products={products} onAddToCart={handleAddToCart} />

        {/* Отображаем корзину */}
        <Cart cart={cart} onIncrease={handleAddToCart} onDecrease={handleDecreaseQuantity} />
      </main>
    </div>
  )
}

export default App

// Проверка автоматического форматирования
