import { useEffect, useState } from 'react'

// Пользовательский хук для управления корзиной
function useCart() {
  // При первом запуске восстанавливаем корзину
  const [cart, setCart] = useState(() => {
    try {
      // Получаем сохранённую строку JSON
      const savedCart = localStorage.getItem('foodCart')

      // Если данных нет, возвращаем пустой массив
      if (!savedCart) {
        return []
      }

      // Преобразуем JSON в JavaScript-данные
      const parsedCart = JSON.parse(savedCart)

      // Убеждаемся, что получили массив
      return Array.isArray(parsedCart) ? parsedCart : []
    } catch {
      // Если чтение не удалось, начинаем с пустой корзины
      return []
    }
  })

  // Сохраняем корзину после каждого изменения
  useEffect(() => {
    localStorage.setItem('foodCart', JSON.stringify(cart))
  }, [cart])

  // Добавляем одну порцию блюда в корзину
  function handleAddToCart(product) {
    setCart((previousCart) => {
      // Ищем блюдо в корзине
      const existingItem = previousCart.find((item) => item.id === product.id)

      // Если остаток ограничен, проверяем доступное количество
      const currentQuantity = existingItem?.quantityInCart ?? 0

      if (product.quantity !== null && currentQuantity >= product.quantity) {
        return previousCart
      }

      // Если блюдо уже есть, увеличиваем количество
      if (existingItem) {
        return previousCart.map((item) =>
          item.id === product.id ? { ...item, quantityInCart: item.quantityInCart + 1 } : item,
        )
      }

      // Если блюда ещё нет, добавляем первую порцию
      return [...previousCart, { ...product, quantityInCart: 1 }]
    })
  }

  // Уменьшаем количество выбранного блюда
  function handleDecreaseQuantity(productId) {
    setCart((previousCart) => {
      return (
        previousCart
          .map((item) => {
            // Другие блюда не изменяем
            if (item.id !== productId) {
              return item
            }

            // Уменьшаем количество на одну порцию
            return {
              ...item,
              quantityInCart: item.quantityInCart - 1,
            }
          })
          // Удаляем блюда, у которых осталось 0 порций
          .filter((item) => item.quantityInCart > 0)
      )
    })
  }

  // Синхронизируем корзину с актуальными данными Django
  function syncCartWithProducts(products) {
    setCart((previousCart) => {
      return previousCart.flatMap((item) => {
        // Находим актуальное блюдо в меню
        const actualProduct = products.find((product) => product.id === item.id)

        // Если блюдо больше недоступно — удаляем из корзины
        if (!actualProduct) {
          return []
        }

        // Определяем, сколько порций можно оставить
        const actualQuantity =
          actualProduct.quantity === null
            ? item.quantityInCart
            : Math.min(item.quantityInCart, actualProduct.quantity)

        // Если остаток равен нулю — удаляем блюдо
        if (actualQuantity <= 0) {
          return []
        }

        // Обновляем данные блюда и сохраняем допустимое количество
        return [
          {
            ...actualProduct,
            quantityInCart: actualQuantity,
          },
        ]
      })
    })
  }

  // Пока возвращаем состояние и функцию его изменения
  return { cart, setCart, handleAddToCart, handleDecreaseQuantity, syncCartWithProducts }
}

export default useCart
