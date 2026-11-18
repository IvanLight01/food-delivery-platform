import { useEffect, useState, useRef } from 'react'
import { getOrders, cancelOrder } from '../services/api'

// Переводим технические статусы Django для покупателя
const ORDER_STATUS_LABELS = {
  NEW: 'Новый',
  CONFIRMED: 'Подтверждён',
  COOKING: 'Готовится',
  READY: 'Готов к доставке',
  DELIVERING: 'Доставляется',
  COMPLETED: 'Завершён',
  CANCELLED: 'Отменён',
}

// Компонент истории заказов покупателя
function OrderHistory({ accessToken, onRefreshToken, refreshKey }) {
  // Список заказов, полученных от Django
  const [orders, setOrders] = useState([])
  // Выполняется ли загрузка заказов
  const [isLoading, setIsLoading] = useState(false)
  // Сообщение об ошибке загрузки
  const [error, setError] = useState('')
  // ID заказа, который сейчас отменяется
  // null означает, что отмена не выполняется
  const [cancellingOrderId, setCancellingOrderId] = useState(null)
  // Защита от повторного запуска отмены заказа
  const isCancellingRef = useRef(false)
  // Номер актуального запроса истории заказов
  const latestRequestIdRef = useRef(0)
  // Ошибка при попытке отменить заказ
  const [cancelError, setCancelError] = useState('')
  // Сообщение об успешной отмене заказа
  const [cancelSuccess, setCancelSuccess] = useState('')
  // Время последней успешной загрузки истории
  const [lastUpdated, setLastUpdated] = useState(null)

  // Загружаем историю заказов из Django
  async function loadOrders() {
    // Увеличиваем номер актуального запроса
    const requestId = ++latestRequestIdRef.current

    // Без Access Token запрос не отправляем
    // Если пользователь не авторизован, очищаем историю
    if (!accessToken) {
      setOrders([])
      setError('')
      setCancelError('')
      setCancelSuccess('')
      setLastUpdated(null)
      return
    }

    try {
      setIsLoading(true)
      setError('')

      // Результат запроса сохраним здесь
      let data

      try {
        // Первый запрос с текущим Access Token
        data = await getOrders(accessToken)
      } catch (err) {
        // Если ошибка не 401 — обновлять токен бессмысленно
        if (err.message !== 'ACCESS_TOKEN_INVALID') {
          throw err
        }

        // Получаем новый Access Token
        const newAccessToken = await onRefreshToken()

        // Если обновление не вернуло токен, повторять запрос нельзя
        if (!newAccessToken) {
          throw new Error('Не удалось обновить авторизацию')
        }

        // Повторяем запрос с обновлённым токеном
        data = await getOrders(newAccessToken)
      }
      // Сохраняем успешно полученные данные
      if (requestId === latestRequestIdRef.current) {
        setOrders(data)
        setLastUpdated(new Date())
      }
    } catch (err) {
      // Ошибку показывает только актуальный запрос
      if (requestId === latestRequestIdRef.current) {
        setError(err.message)
      }
    } finally {
      // Только актуальный запрос завершает загрузку
      if (requestId === latestRequestIdRef.current) {
        setIsLoading(false)
      }
    }
  }

  // Автоматически загружаем заказы после входа
  useEffect(() => {
    loadOrders()
  }, [accessToken, refreshKey])

  // Отменяем выбранный заказ
  async function handleCancelOrder(orderId) {
    // Если отмена уже выполняется, повторный вызов запрещён
    if (isCancellingRef.current) {
      return
    }
    // Спрашиваем покупателя, действительно ли он хочет отменить заказ
    const isConfirmed = window.confirm(`Вы уверены, что хотите отменить заказ №${orderId}?`)

    // Если нажали «Отмена», запрос в Django не отправляем
    if (!isConfirmed) {
      return
    }
    // Мгновенно блокируем повторные вызовы
    isCancellingRef.current = true

    try {
      // Запоминаем, какой заказ сейчас отменяется
      setCancellingOrderId(orderId)
      // Убираем предыдущую ошибку отмены
      setCancelError('')
      // Очищаем сообщение от предыдущей успешной отмены
      setCancelSuccess('')

      // Отправляем запрос на отмену в Django
      try {
        // Сначала пробуем отменить заказ с текущим токеном
        await cancelOrder(accessToken, orderId)
      } catch (err) {
        // Если ошибка не связана с JWT, передаём её внешнему catch
        if (err.message !== 'ACCESS_TOKEN_INVALID') {
          throw err
        }

        // Получаем новый Access Token
        const newAccessToken = await onRefreshToken()

        // Проверяем, что обновление прошло успешно
        if (!newAccessToken) {
          throw new Error('Не удалось обновить авторизацию')
        }

        // Повторяем отмену с новым токеном
        await cancelOrder(newAccessToken, orderId)
      }
      // Сообщаем покупателю об успешной отмене
      setCancelSuccess(`Заказ №${orderId} успешно отменён`)

      // После отмены получаем обновлённую историю
      await loadOrders()
    } catch (err) {
      // Показываем сообщение, если отменить заказ не удалось
      setCancelError(err.message)
    } finally {
      // Снимаем блокировку после успеха или ошибки
      isCancellingRef.current = false

      // Возвращаем обычное состояние кнопок
      setCancellingOrderId(null)
    }
  }

  return (
    <section>
      <h2>История заказов</h2>

      {/* Кнопка для ручного обновления истории */}
      <button type="button" onClick={loadOrders} disabled={isLoading}>
        {isLoading ? 'Обновляем...' : 'Обновить историю'}
      </button>

      {/* Показываем сообщение, пока Django возвращает заказы */}
      {isLoading && <p role="status">⏳ Загружаем историю заказов...</p>}

      {/* Показываем ошибку загрузки истории */}
      {error && (
        <div role="alert">
          <p>❌ {error}</p>

          {/* Если заказы уже были загружены, предупреждаем об устаревших данных */}
          {orders.length > 0 && (
            <p>
              ⚠️ Показана ранее загруженная история. Данные могли измениться. Попробуйте обновить
              список.
            </p>
          )}
        </div>
      )}

      {/* Отдельное сообщение об ошибке отмены заказа */}
      {cancelError && <p role="alert">❌ Ошибка отмены заказа: {cancelError}</p>}

      {/* Сообщение об успешной отмене заказа */}
      {cancelSuccess && <p role="status">✅ {cancelSuccess}</p>}

      {/*  показываем количество заказов */}
      <p>Количество заказов: {orders.length}</p>

      {/* Показываем время последней успешной загрузки */}
      {lastUpdated && <p>Последнее обновление: {lastUpdated.toLocaleTimeString('ru-RU')}</p>}

      {/* Показываем сообщение, если загрузка завершилась успешно,
          но у пользователя пока нет заказов */}
      {!isLoading && !error && orders.length === 0 && (
        <p>🍕 У вас пока нет заказов. Выберите что-нибудь вкусное!</p>
      )}

      {/* Показываем каждый заказ из массива */}
      {orders.map((order) => (
        <article key={order.id}>
          {/* Уникальный номер заказа */}
          <h3>Заказ №{order.id}</h3>
          {/* Дата и время создания заказа */}
          <p>Дата заказа: {new Date(order.created_at).toLocaleString('ru-RU')}</p>
          {/* Текущий статус из Django */}
          {/* Показываем понятное название статуса */}
          <p>Статус: {ORDER_STATUS_LABELS[order.status] ?? order.status}</p>

          {/* Адрес доставки */}
          <p>Адрес: {order.delivery_address}</p>

          {/* Итоговая сумма заказа */}
          <p>Сумма: {order.total_price} ₽</p>

          {/* Отменять через интерфейс разрешаем только новые заказы */}
          {order.status === 'NEW' && (
            <button
              type="button"
              onClick={() => handleCancelOrder(order.id)}
              disabled={cancellingOrderId !== null}
            >
              {cancellingOrderId === order.id ? 'Отменяем заказ...' : 'Отменить заказ'}
            </button>
          )}

          {/* Список блюд внутри конкретного заказа */}
          <h4>Состав заказа:</h4>

          <ul>
            {order.items.map((item) => (
              <li key={item.id}>
                {/* Название блюда на момент покупки */}
                {item.product_name}
                {/* Количество заказанных порций */}
                {' — '}
                {item.quantity} шт.
                {/* Стоимость позиции */}
                {' — '}
                {item.line_total} ₽
              </li>
            ))}
          </ul>
          <hr />
        </article>
      ))}
    </section>
  )
}

export default OrderHistory
