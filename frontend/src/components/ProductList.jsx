// Импортируем компонент одной карточки
import ProductCard from './ProductCard'

// Получаем список блюд и функцию добавления в корзину
function ProductList({ products, onAddToCart }) {
  return (
    <div className="products">
      {/* Перебираем все блюда */}
      {products.map((product) => (
        <ProductCard key={product.id} product={product} onAddToCart={onAddToCart} />
      ))}
    </div>
  )
}

export default ProductList // Импортируем компонент одной карточки
