from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db.models import Q
from .models import Product
from .serializers import ProductSerializer, CategorySerializer, Category


class CategoryViewSet(viewsets.ViewSet):

    @swagger_auto_schema(
        operation_description="Retrieve all categories",
        responses={200: CategorySerializer(many=True)},
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
        serializer.save()  # Manually save the serializer in `ViewSet`
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
        category = request.query_params.get('category')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        search = request.query_params.get('search')

        if category:
            queryset = queryset.filter(category__name=category)
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

        serializer = ProductSerializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        request_body=ProductSerializer,
        responses={201: ProductSerializer, 400: "Bad Request"},
        operation_description="Create a new product."
    )
    def create(self, request):
        serializer = ProductSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        request_body=ProductSerializer,
        responses={200: ProductSerializer, 404: "Product not found", 400: "Bad Request"},
        operation_description="Update an existing product by ID."
    )
    def update(self, request, pk=None):
        product = Product.objects.filter(pk=pk).first()
        if not product:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProductSerializer(product, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    @swagger_auto_schema(
        responses={204: "No Content", 404: "Product not found"},
        operation_description="Delete a product by ID."
    )
    def destroy(self, request, pk):
        product = Product.objects.filter(pk=pk).first()
        if not product:
            return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
