from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('rate/<int:item_id>/', views.rate_item, name='rate_item'),
    path('posts/', views.PostListView.as_view(), name='post_list'),
    path('posts/create/', views.post_create, name='post_create'),
    path('posts/<int:post_id>/', views.PostDetailView.as_view(), name='post_detail'),
    path('posts/<int:pk>/delete/', views.PostDeleteView.as_view(), name='post_delete'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('about/', views.about_view, name='about'),
    path('logout/', views.logout_view, name='logout'),
]
