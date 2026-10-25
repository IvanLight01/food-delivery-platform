
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet


# DefaultRouter автоматически создаст маршруты для списка и отдельных объектов.
router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('products', ProductViewSet, basename='product')

urlpatterns = router.urls