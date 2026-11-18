import { useEffect, useRef, useState } from 'react' // useRef позволяет хранить значение между рендерами
import { prepareOrderData, createOrder, generateIdempotencyKey } from '../services/api'

// Получаем корзину и токен от родительского App
function CheckoutForm({ cartItems, accessToken, onOrderSuccess, onRefreshToken }) {
  // Храним адрес, который вводит покупатель
  const [deliveryAddress, setDeliveryAddress] = useState('')
  // Выполняется ли сейчас отправка заказа
  const [isSubmitting, setIsSubmitting] = useState(false)
  // Сообщение об успешном оформлении или ошибке
  const [message, setMessage] = useState('')
  // Храним ключ текущей попытки оформления заказа
  // null означает, что ключ ещё не создан
  const idempotencyKeyRef = useRef(null)
  // Запоминаем данные, для которых создали ключ
  const orderPayloadRef = useRef(null)
  // Был ли заказ успешно оформлен
  const [isOrderSuccessful, setIsOrderSuccessful] = useState(false)

  // После успешного заказа ждём, когда покупатель соберёт новую корзину
  useEffect(() => {
    // Если прежний заказ завершён и появились новые товары
    if (isOrderSuccessful && cartItems.length > 0) {
      // Разрешаем оформить следующий заказ
      setIsOrderSuccessful(false)

      // Убираем сообщение о предыдущем заказе
      setMessage('')

      // Сбрасываем ключ предыдущего заказа
      idempotencyKeyRef.current = null
      orderPayloadRef.current = null
    }
  }, [cartItems, isOrderSuccessful])
  // Обрабатываем нажатие кнопки «Оформить заказ»
  // Асинхронный обработчик оформления заказа
  async function handleSubmit(event) {
    // Отменяем стандартную отправку HTML-формы
    event.preventDefault()

    // Без авторизации заказ оформлять нельзя
    if (!accessToken) {
      alert('❌ Сначала войдите в аккаунт, чтобы оформить заказ')
      return
    }
    // Проверяем, есть ли блюда в корзине
    if (cartItems.length === 0) {
      // Показываем сообщение без запроса к Django
      setMessage('❌ Добавьте хотя бы одно блюдо в корзину')
      return
    }
    // Преобразуем корзину и адрес в формат Django
    // Убираем пробелы в начале и конце адреса
    const cleanAddress = deliveryAddress.trim()

    // Проверяем, что адрес не состоит только из пробелов
    if (!cleanAddress) {
      setMessage('❌ Укажите корректный адрес доставки')
      return
    }

    // Подготавливаем заказ с очищенным адресом
    const orderData = prepareOrderData(cartItems, cleanAddress)
    // Превращаем данные заказа в строку для сравнения
    const currentPayload = JSON.stringify(orderData)

    // Новый заказ или изменились данные — нужен новый ключ
    if (idempotencyKeyRef.current === null || orderPayloadRef.current !== currentPayload) {
      idempotencyKeyRef.current = generateIdempotencyKey()

      // Запоминаем данные, соответствующие новому ключу
      orderPayloadRef.current = currentPayload
    }
    // Получаем ключ текущей попытки оформления заказа
    const idempotencyKey = idempotencyKeyRef.current

    // Пока проверяем только наличие ключа, не показывая его целиком
    console.log('Ключ заказа создан:', Boolean(idempotencyKey))

    // Не отправляем ещё один запрос, пока предыдущий обрабатывается
    if (isSubmitting) {
      return
    }

    try {
      // Блокируем кнопку и очищаем предыдущее сообщение
      setIsSubmitting(true)
      setMessage('⏳ Оформляем заказ...')

      // Переменная для результата создания заказа
      let order

      try {
        // Первая попытка — с текущим Access Token
        order = await createOrder(accessToken, orderData, idempotencyKey)
      } catch (err) {
        // Если ошибка не связана с JWT, передаём её во внешний catch
        if (err.message !== 'ACCESS_TOKEN_INVALID') {
          throw err
        }

        // Получаем новый Access Token через Refresh Token
        const newAccessToken = await onRefreshToken()

        // Повторяем запрос с новым токеном,
        // но обязательно с тем же Idempotency-Key
        order = await createOrder(newAccessToken, orderData, idempotencyKey)
      }
      // Django подтвердил создание или возврат существующего заказа
      setMessage(`✅ Заказ №${order.id} успешно оформлен!`)
      // Django подтвердил заказ — запрещаем повторное оформление
      setIsOrderSuccessful(true)
      // Очищаем корзину только после подтверждения заказа Django
      onOrderSuccess()
    } catch (err) {
      // Показываем ошибку, если заказ не удалось оформить
      setMessage(`❌ ${err.message}`)
    } finally {
      // Разблокируем кнопку после завершения запроса
      setIsSubmitting(false)
    }
  }

  return (
    <section>
      <h2>Оформление заказа</h2>
      {/* Показываем сообщение, только если оно не пустое */}
      {message && <p role="status">{message}</p>}
      <form onSubmit={handleSubmit}>
        <label htmlFor="delivery-address">Адрес доставки</label>
        <input
          id="delivery-address"
          type="text"
          value={deliveryAddress}
          onChange={(event) => setDeliveryAddress(event.target.value)}
          placeholder="Улица, дом, квартира"
          required
        />
        {/* Кнопка оформления заказа */}
        <button type="submit" disabled={isSubmitting || isOrderSuccessful}>
          {isSubmitting
            ? 'Оформляем заказ...'
            : isOrderSuccessful
              ? 'Заказ оформлен'
              : 'Оформить заказ'}
        </button>{' '}
      </form>
    </section>
  )
}

export default CheckoutForm
