from django.urls import path

urlpatterns = [
    path('register/', include('e_shop.urls')),
    path('login/', include('e_shop.urls')),
]
