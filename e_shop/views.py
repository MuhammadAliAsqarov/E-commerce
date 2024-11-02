from django.core.cache import cache
from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from users.permissions import is_admin
from .models import Product, Cart, Payment
from .serializers import Category, CartSerializer, ProductDestroySerializer
from rest_framework import viewsets, status
from rest_framework.response import Response
from .serializers import ProductSerializer, ProductCreateSerializer, CartListSerializer, PaymentSerializer, \
    CategorySerializer
from .custom_pagination import CustomPagination
from exceptions.error_codes import ErrorCodes
from exceptions.exception import CustomApiException
from .utils import get_cached_cart_data, calculate_cart_totals, paginate_and_cache_cart_response, fetch_or_create_cart, \
    validate_products_data, add_products_to_cart, clear_cart_cache, get_cart, get_cart_item, update_or_remove_cart_item


class CategoryViewSet(viewsets.ViewSet):
    @swagger_auto_schema(
        operation_description="Retrieve all categories",
        responses={200: CategorySerializer(many=True)}
    )
    def list(self, request):
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response({"message": "Successfully retrieved all categories", "data": serializer.data},
                        status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Create a new category",
        request_body=CategorySerializer,
        responses={201: CategorySerializer()},
    )
    def create(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Category created successfully", "data": serializer.data},
                        status=status.HTTP_201_CREATED)


class ProductViewSet(viewsets.ViewSet):
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('category', openapi.IN_QUERY, description="Filter by category", type=openapi.TYPE_STRING),
            openapi.Parameter('min_price', openapi.IN_QUERY, description="Filter by minimum price",
                              type=openapi.TYPE_NUMBER),
            openapi.Parameter('max_price', openapi.IN_QUERY, description="Filter by maximum price",
                              type=openapi.TYPE_NUMBER),
            openapi.Parameter('search', openapi.IN_QUERY, description="Search by name or description",
                              type=openapi.TYPE_STRING),
        ],
        responses={200: ProductSerializer(many=True)},
        operation_description="Retrieve a list of products with optional filters for category, price range, and search term."
    )
    def list(self, request):
        queryset = Product.objects.all()
        filters = {}
        category = request.query_params.get('category')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        search = request.query_params.get('search')
        if category:
            filters['category__name'] = category
        if min_price:
            filters['price__gte'] = min_price
        if max_price:
            filters['price__lte'] = max_price
        queryset = queryset.filter(**filters)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))
        paginator = CustomPagination()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = ProductSerializer(paginated_queryset, many=True) if paginated_queryset else ProductSerializer(
            queryset, many=True)

        return paginator.get_paginated_response(serializer.data) if paginated_queryset else Response(serializer.data)

    @swagger_auto_schema(
        request_body=ProductCreateSerializer,
        responses={201: ProductCreateSerializer(many=True), 400: "Bad Request"},
        operation_description="Create multiple products for a single category at once."
    )
    @is_admin
    def create(self, request):
        serializer = ProductCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        products = serializer.save()
        return Response(
            {"message": "Products created successfully", "data": ProductSerializer(products, many=True).data},
            status=status.HTTP_201_CREATED
        )

    @swagger_auto_schema(
        request_body=ProductDestroySerializer,
        responses={204: "No Content", 400: "Bad Request"},
        operation_description="Delete multiple products by their IDs within a specific category."
    )
    def destroy(self, request, category_id):
        serializer = ProductDestroySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        product_ids = serializer.validated_data['product_ids']
        if not Category.objects.filter(id=category_id).exists():
            raise CustomApiException(ErrorCodes.NOT_FOUND.value, message='Category Not Found')
        products = Product.objects.filter(id__in=product_ids, category_id=category_id)
        if not products.exists():
            raise CustomApiException(ErrorCodes.NOT_FOUND.value,
                                     message='No products found for the given IDs in this category.')
        products.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartViewSet(viewsets.ViewSet):
    pagination_class = CustomPagination

    def list(self, request):
        cart_data = get_cached_cart_data(request.user)
        if cart_data:
            return Response(cart_data)
        cart, created = Cart.objects.get_or_create(user=request.user)
        serializer = CartListSerializer(cart)
        total_items, total_price = calculate_cart_totals(cart)
        response_data = serializer.data
        response_data['total_items'] = total_items
        response_data['total_price'] = f"{total_price:.2f}"
        paginated_response = paginate_and_cache_cart_response(request, response_data, f'cart_{request.user.id}')
        return paginated_response

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'products': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'product_id': openapi.Schema(type=openapi.TYPE_INTEGER,
                                                         description='ID of the product to add'),
                            'quantity': openapi.Schema(type=openapi.TYPE_INTEGER,
                                                       description='Quantity of the product'),
                        },
                        required=['product_id', 'quantity'],
                    ),
                ),
            },
            required=['products'],
        ),
        responses={200: CartSerializer, 404: "One or more products not found"},
        operation_description="Add multiple products to the cart."
    )
    def add_product(self, request):
        cart = get_cart(request.user)
        if not cart:
            raise CustomApiException(ErrorCodes.NOT_FOUND.value, message="You don't have a cart.")
        products_data = request.data.get("products", [])
        validation_error = validate_products_data(products_data)
        if validation_error:
            return Response(validation_error, status=status.HTTP_400_BAD_REQUEST)
        add_products_to_cart(cart, products_data)
        clear_cart_cache(request.user.id)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'product_id': openapi.Schema(type=openapi.TYPE_INTEGER,
                                             description="ID of the product to update or remove"),
                'quantity': openapi.Schema(type=openapi.TYPE_INTEGER, description="Quantity to decrease (optional)")
            },
            required=['product_id'],
        ),
        responses={200: CartSerializer, 404: "Product not in cart or no cart found"},
        operation_description="Decrease quantity of a product or remove it from the cart if quantity reaches zero."
    )
    def update_or_remove_product(self, request):
        cart = get_cart(request.user)
        if not cart:
            raise CustomApiException(ErrorCodes.NOT_FOUND.value, message="You don't have a cart.")
        product_id = request.data.get("product_id")
        quantity = request.data.get("quantity", 1)
        cart_item = get_cart_item(cart, product_id)
        if not cart_item:
            raise CustomApiException(ErrorCodes.NOT_FOUND.value, message="Product not in cart.")
        update_or_remove_cart_item(cart_item, quantity)
        cache_key = f'cart_{request.user.id}'
        cache.delete(cache_key)
        serializer = CartSerializer(cart)
        return Response(serializer.data)


class PaymentViewSet(viewsets.ViewSet):
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'amount': openapi.Schema(type=openapi.TYPE_NUMBER, description='Total amount to be charged'),
                'payment_method': openapi.Schema(type=openapi.TYPE_STRING,
                                                 description='Payment method (e.g., credit card, PayPal)'),
                'card_details': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'card_number': openapi.Schema(type=openapi.TYPE_STRING, description='Card number'),
                        'expiry_date': openapi.Schema(type=openapi.TYPE_STRING,
                                                      description='Expiry date in MM/YYYY format'),
                        'cvv': openapi.Schema(type=openapi.TYPE_STRING, description='CVV code'),
                    },
                    required=['card_number', 'expiry_date', 'cvv'],
                ),
            },
            required=['amount', 'payment_method', 'card_details'],
        ),
        responses={
            200: PaymentSerializer,
            400: openapi.Response("Invalid payment data"),
            404: openapi.Response("Cart not found"),
        },
        operation_description="Process payment for the user's cart."
    )
    def create(self, request):
        amount = request.data.get("amount")
        payment_method = request.data.get("payment_method")
        card_details = request.data.get("card_details")
        if not amount or not payment_method or not card_details:
            return Response({"detail": "Amount, payment method, and card details are required."},
                            status=status.HTTP_400_BAD_REQUEST)
        cart = Cart.objects.filter(user=request.user).first()
        if not cart:
            return Response({"detail": "Cart not found."}, status=status.HTTP_404_NOT_FOUND)
        payment = Payment.objects.create(
            user=request.user,
            amount=amount,
            payment_method=payment_method,
            status='processed'
        )
        cart.cartitem_set.all().delete()
        cache_key = f'payment_{request.user.id}'
        cache.set(cache_key, payment.id, timeout=60 * 15)
        serializer = PaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)
