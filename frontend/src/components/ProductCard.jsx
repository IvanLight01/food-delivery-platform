// Компонент отображает одно блюдо
function ProductCard({ product, onAddToCart }) {
  return (
    <div className="product-card">
      {/* Название блюда */}
      <h3>{product.name}</h3>

      {/* Описание */}
      <p>{product.description}</p>

      {/* Цена */}
      <p>
        <strong>Цена: {product.price} ₽</strong>
      </p>

      {/* Кнопка добавления в корзину */}
      <button onClick={() => onAddToCart(product)}>В корзину</button>
    </div>
  )
}

// Позволяет импортировать компонент в другие файлы
export default ProductCard
