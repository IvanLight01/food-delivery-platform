from django.db import models


class Category(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Название'
    )

    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, # связь OneToMany
        on_delete=models.PROTECT, # не удалит Категорию, если есть в ней блюда
        related_name='products', # обратная связь (от категории к блюдам)
        verbose_name='Категория'
    )

    name = models.CharField(
        max_length=200,
        verbose_name='Название'
    )

    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Цена'
    )

    weight = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Вес или объём в граммах/мл'
    )

    unit = models.CharField(
        max_length=10,
        default='гр.',
        verbose_name='Единица измерения'
    )

    quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Количество штук/порций'
    )

    image = models.ImageField(
        upload_to='products/',
        blank=True,
        null=True,
        verbose_name='Изображение'
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='Активно'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата изменения'
    )

    def __str__(self):
        return self.name

    class Meta:
        # Второй уровень защиты от отрицательной цены
        # PostgreSQL не позволяет записать неправильные данные ни одним способом
        constraints = [
            models.CheckConstraint(
                # Цена должна быть больше или равна нулю
                condition=models.Q(price__gte=0),
                name='product_price_non_negative'
            )
        ]