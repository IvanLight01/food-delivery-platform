// Компонент одного блюда внутри корзины
function CartItem({ item, onIncrease, onDecrease }) {
  return (
    <div className="cart-item">
      {/* Название блюда */}
      <h3>{item.name}</h3>

      {/* Цена одной порции */}
      <p>Цена: {item.price} ₽</p>

      {/* Управление количеством */}
      <div className="cart-quantity">
        <button onClick={() => onDecrease(item.id)}>−</button>

        <span>{item.quantityInCart}</span>

        <button onClick={() => onIncrease(item)}>+</button>
      </div>
    </div>
  )
}

export default CartItem
