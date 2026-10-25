
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .permissions import IsCookOrAdminOrReadOnly

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet): #
    queryset = Category.objects.filter(is_active=True) # выбирает только активные категории и блюда.
    serializer_class = CategorySerializer # определяет формат JSON.
    permission_classes = [AllowAny] # разрешает запросы без авторизации


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    permission_classes = [IsCookOrAdminOrReadOnly]

    @action(detail=False, methods=['get'])
    def expensive(self, request):
        expensive_products = self.get_queryset().filter(price__gte=1000)
        serializer = self.get_serializer(expensive_products, many=True)
        return Response(serializer.data)