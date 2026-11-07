from rest_framework import serializers
from .models import Category, Product

""" Берем Django-модель и автоматически создаем сериализатор для её полей """

# преобразует категории в формат JSON.
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = (
            'id',
            'name',
            'description',
            'is_active',
            'created_at',
        )
        # Эти поля устанавливает сама база данных / Django
        read_only_fields = ('id', 'created_at')


# преобразует блюда в JSON
class ProductSerializer(serializers.ModelSerializer):
    # Цена блюда не может быть отрицательной
    price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0
    )

    class Meta:
        model = Product
        fields = (
            'id',
            'category',
            'name',
            'description',
            'price',
            'weight',
            'unit',
            'quantity',
            'image',
            'is_active',
            'created_at',
            'updated_at',
        )
        # Покупатель или сотрудник не задаёт эти значения вручную
        read_only_fields = ('id', 'created_at', 'updated_at')