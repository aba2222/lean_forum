from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('rate/<int:item_id>/', views.rate_item, name='rate_item'),
    path('posts/', views.post_list, name='post_list'),
    path('posts/create/', views.post_create, name='post_create'),
    path('posts/<int:post_id>/', views.post_detail, name='post_detail'),
]
