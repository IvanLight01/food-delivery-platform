import CartItem from './CartItem'

// ОТОБРАЖАЕТ СОДЕРЖИМОЕ КОРЗИНЫ
function Cart({ cart, onIncrease, onDecrease }) {
  // Считаем общую стоимость всех блюд в корзине
  const totalPrice = cart.reduce((total, item) => {
    // Цена приходит из Django строкой, например "1100.00"
    const price = Number(item.price)

    // Стоимость блюда = цена × количество порций
    const itemTotal = price * item.quantityInCart

    // Прибавляем стоимость блюда к общей сумме
    return total + itemTotal
  }, 0)
  return (
    <section className="cart">
      <h2>🛒 Ваша корзина</h2>

      {/* Если корзина пустая */}
      {cart.length === 0 && <p>Корзина пока пуста.</p>}

      {cart.map((item) => (
        <CartItem key={item.id} item={item} onIncrease={onIncrease} onDecrease={onDecrease} />
      ))}

      {/* Итоговая стоимость корзины */}
      <div className="cart-total">
        <h3>Итого: {totalPrice.toFixed(2)} ₽</h3>{' '}
        {/* Метод .toFixed(2) отображает число с двумя знаками после запятой. */}
      </div>
    </section>
  )
}

export default Cart
