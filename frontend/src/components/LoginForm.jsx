import { useState } from 'react'
import { loginUser } from '../services/api'

// Получаем функцию из App через props
function LoginForm({ onLoginSuccess }) {
  // Логин, который вводит пользователь
  const [username, setUsername] = useState('')
  // Пароль, который вводит пользователь
  const [password, setPassword] = useState('')
  // Сообщение о результате входа
  const [message, setMessage] = useState('')
  // true означает, что запрос входа выполняется
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Отправляем данные формы на Django
  // Обрабатываем отправку формы
  async function handleSubmit(event) {
    // Запрещаем стандартную перезагрузку страницы
    event.preventDefault()

    // Если запрос уже выполняется — повторно не отправляем
    if (isSubmitting) {
      return
    }
    // Очищаем старое сообщение
    setMessage('')
    // Блокируем повторную отправку
    setIsSubmitting(true)

    try {
      // Отправляем логин и пароль Django
      const tokens = await loginUser(username, password)

      // Проверяем наличие токенов
      if (!tokens.access || !tokens.refresh) {
        throw new Error('Сервер не вернул токены авторизации')
      }

      // Передаём токены в App.jsx
      // await позволяет дождаться загрузки профиля
      await onLoginSuccess(tokens)

      // Показываем успешный результат
      setMessage('✅ Вход выполнен успешно!')

      // Очищаем пароль
      setPassword('')
    } catch (err) {
      // Показываем ошибку пользователю
      setMessage(`❌ ${err.message}`)
    } finally {
      // Разблокируем кнопку после завершения запроса
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <h2>Вход в аккаунт</h2>
      {/* Поле логина */}
      <input
        type="text"
        placeholder="Логин"
        value={username}
        onChange={(event) => setUsername(event.target.value)}
      />
      {/* Поле пароля */}
      <input
        type="password"
        placeholder="Пароль"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      {/* disabled={isSubmitting} блокирует кнопку, когда isSubmitting === true */}
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Входим...' : 'Войти'}
      </button>
      {/* Показываем результат авторизации */}
      {message && <p role="status">{message}</p>}
    </form>
  )
}

export default LoginForm
