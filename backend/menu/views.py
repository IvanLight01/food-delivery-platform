
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .permissions import IsCookOrAdminOrReadOnly

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


class CategoryViewSet(viewsets.ModelViewSet): # ModelViewSet добавляет операции создания, редактирования и удаления

    serializer_class = CategorySerializer # Сериализатор для преобразования данных в JSON
    permission_classes = [IsCookOrAdminOrReadOnly] # Читать могут все, изменять — повар и администратор

    def get_queryset(self):
        """Определяем, какие категории видит пользователь."""

        user = self.request.user

        # Повар и администратор видят все категории
        if user.is_authenticated:
            if user.role in ('COOK', 'ADMIN') or user.is_superuser:
                return Category.objects.all()

        # Покупатель и гость видят только активные категории
        return Category.objects.filter(is_active=True)




class ProductViewSet(viewsets.ModelViewSet):

    serializer_class = ProductSerializer
    permission_classes = [IsCookOrAdminOrReadOnly]

    def get_queryset(self):
        """Определяем, какие блюда доступны пользователю."""

        user = self.request.user

        # Повар и администратор видят все блюда, включая временно скрытые и отключенные категории
        if user.is_authenticated:
            if user.role in ('COOK', 'ADMIN') or user.is_superuser:
                return Product.objects.all()

        # Покупатели и гости видят только активные блюда, которые находятся в активных категориях
        return Product.objects.filter(
            is_active=True,
            category__is_active=True # Двойное подчёркивание __ позволяет Django обращаться к полям связанной модели
        )

    @action(detail=False, methods=['get'])
    def expensive(self, request):
        expensive_products = self.get_queryset().filter(price__gte=1000)
        serializer = self.get_serializer(expensive_products, many=True)
        return Response(serializer.data)