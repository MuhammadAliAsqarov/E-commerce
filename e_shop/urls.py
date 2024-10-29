from django.urls import path
from .views import ProductViewSet, CartViewSet

product_list = ProductViewSet.as_view({'get': 'list', 'post': 'create'})
product_detail = ProductViewSet.as_view({'put': 'update', 'delete': 'destroy'})
cart_list = CartViewSet.as_view({'get': 'list'})
cart_add = CartViewSet.as_view({'post': 'add_product'})
cart_remove = CartViewSet.as_view({'delete': 'remove_product'})

urlpatterns = [
    path('products/', product_list, name='product-list'),
    path('products/<int:pk>/', product_detail, name='product-detail'),
    path('cart/', cart_list, name='cart-list'),
    path('cart/add/', cart_add, name='cart-add'),
    path('cart/remove/<int:pk>/', cart_remove, name='cart-remove'),
]

