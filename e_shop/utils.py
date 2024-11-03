from django.core.cache import cache
from .custom_pagination import CustomPagination
from .models import Product, CartItem, Cart


def get_cached_cart_data(user):
    cache_key = f'cart_{user.id}'
    return cache.get(cache_key)


def calculate_cart_totals(cart):
    total_items = sum(cart_item.quantity for cart_item in cart.cartitem_set.all())
    total_price = sum(cart_item.quantity * cart_item.product.price for cart_item in cart.cartitem_set.all())
    return total_items, total_price


def paginate_and_cache_cart_response(request, response_data, cache_key, timeout=60 * 15):
    paginator = CustomPagination()
    data_list = [response_data]
    paginated_data = paginator.paginate_queryset(data_list, request)
    cache.set(cache_key, paginated_data, timeout=timeout)
    return paginator.get_paginated_response(paginated_data)


def fetch_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def validate_products_data(products_data):
    if not products_data:
        return {"detail": "No products provided."}

    for product_data in products_data:
        product_id = product_data.get("product_id")
        if not Product.objects.filter(id=product_id).exists():
            return {"detail": f"Product with ID {product_id} not found."}

    return None


def add_products_to_cart(cart, products_data):
    for product_data in products_data:
        product_id = product_data["product_id"]
        quantity = product_data.get("quantity", 1)

        product = Product.objects.get(id=product_id)
        cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)

        if not created:
            cart_item.quantity += quantity
        else:
            cart_item.quantity = quantity

        cart_item.total_price = cart_item.quantity * product.price
        cart_item.save()


def clear_cart_cache(user_id):
    cache_key = f'cart_{user_id}'
    cache.delete(cache_key)


def get_cart(user):
    return Cart.objects.filter(user=user).first()


def get_cart_item(cart, product_id):
    return CartItem.objects.filter(cart=cart, product_id=product_id).first()


def update_or_remove_cart_item(cart_item, quantity):
    cart_item.quantity -= quantity
    if cart_item.quantity <= 0:
        cart_item.delete()
    else:
        cart_item.save()
