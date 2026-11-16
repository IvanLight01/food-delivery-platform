import { useState } from 'react'
import { registerUser } from '../services/api'

// Компонент регистрации нового пользователя
function RegisterForm({ onRegisterSuccess }) {
  // Храним все введённые данные в одном объекте
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    password_confirm: '',
    first_name: '',
    last_name: '',
    phone: '',
  })
  // Сообщение об успехе или ошибке регистрации
  const [message, setMessage] = useState('')
  // Показывает, выполняется ли сейчас запрос
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [fieldErrors, setFieldErrors] = useState({})

  // Обновляем конкретное поле формы
  function handleChange(event) {
    // name — название изменённого поля
    // value — введённый пользователем текст
    const { name, value } = event.target

    // Создаём новое состояние на основе предыдущего
    setFormData((previousData) => ({
      ...previousData, // Копируем прежние поля
      [name]: value, // Обновляем только нужное поле
    }))
    // Убираем старую ошибку изменённого поля
    setFieldErrors((previousErrors) => ({
      ...previousErrors,
      [name]: undefined,

      // В Django ошибка несовпадения паролей
      // возвращается под ключом password.
      // Поэтому при изменении любого пароля очищаем её.
      ...(name === 'password' || name === 'password_confirm' ? { password: undefined } : {}),
    }))
  }

  // Обрабатываем отправку регистрационной формы
  async function handleSubmit(event) {
    // Отменяем стандартную перезагрузку страницы
    event.preventDefault()

    // Не допускаем повторной отправки
    if (isSubmitting) {
      return
    }

    // Очищаем сообщение от предыдущей попытки
    setMessage('')
    // Убираем старые ошибки полей перед новым запросом
    setFieldErrors({})
    // Блокируем кнопку на время запроса
    setIsSubmitting(true)

    try {
      // Отправляем объект со всеми полями в Django
      await registerUser(formData)

      // Django успешно создал пользователя
      setMessage('✅ Регистрация прошла успешно! Теперь можно войти.')

      // Очищаем форму после успешной регистрации
      setFormData({
        username: '',
        email: '',
        password: '',
        password_confirm: '',
        first_name: '',
        last_name: '',
        phone: '',
      })
      // Сообщаем App, что регистрация завершилась успешно
      onRegisterSuccess()
    } catch (err) {
      // Если Django прислал ошибки отдельных полей
      if (err.fields) {
        // Сохраняем весь объект ошибок
        // Например: { username: ['Логин занят'] }
        setFieldErrors(err.fields)
      } else {
        // Если сервер недоступен или возникла другая ошибка
        setMessage(`❌ ${err.message}`)
      }
    } finally {
      // Разблокируем кнопку при любом результате
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <h2>Регистрация</h2>
      <input
        name="username"
        placeholder="Логин"
        value={formData.username}
        onChange={handleChange}
        required
      />
      {/* Показываем первую ошибку логина */}
      {fieldErrors.username?.[0] && <p role="alert">❌ {fieldErrors.username[0]}</p>}
      <input
        name="email"
        type="email"
        placeholder="Email"
        value={formData.email}
        onChange={handleChange}
        required
      />
      <input
        name="password"
        type="password"
        placeholder="Пароль"
        value={formData.password}
        onChange={handleChange}
        minLength={8}
        required
      />
      <input
        name="password_confirm"
        type="password"
        placeholder="Повторите пароль"
        value={formData.password_confirm}
        onChange={handleChange}
        minLength={8}
        required
      />
      {/* Ошибка несовпадения паролей */}
      {fieldErrors.password?.[0] && <p role="alert">❌ {fieldErrors.password[0]}</p>}
      <input
        name="first_name"
        placeholder="Имя"
        value={formData.first_name}
        onChange={handleChange}
        required
      />
      <input
        name="last_name"
        placeholder="Фамилия"
        value={formData.last_name}
        onChange={handleChange}
        required
      />

      <input
        name="phone"
        type="tel"
        placeholder="Телефон"
        value={formData.phone}
        onChange={handleChange}
      />
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Регистрируем...' : 'Зарегистрироваться'}
      </button>
      {/* Показываем результат регистрации */}
      {message && <p role="status">{message}</p>}
    </form>
  )
}

export default RegisterForm
