from django.urls import include, path
from . import views, api

urlpatterns = [
    path('', views.index, name='index'),
    path('rate/<int:item_id>/', views.rate_item, name='rate_item'),
    path('posts/', views.post_list, name='post_list'),
    path('posts/create/', views.post_create, name='post_create'),
    path('posts/<int:post_id>/', views.PostDetailView.as_view(), name='post_detail'),
    path('posts/<int:pk>/delete/', views.PostDeleteView.as_view(), name='post_delete'),
    path('posts/<int:post_id>/edit/', views.post_edit_view, name='post_edit'),
    path('posts/<int:post_id>/add-to-collection/', views.post_add_to_collection, name='post_add_to_collection'),
    path('comments/<int:comment_id>/delete/', views.comment_delete_view, name='comment_delete'),
    path('comments/<int:comment_id>/edit/', views.comment_edit_view, name='comment_edit'),
    path('collections/', views.collection_list, name='collection_list'),
    path('collections/create/', views.collection_create, name='collection_create'),
    path('collections/<int:collection_id>/', views.collection_detail, name='collection_detail'),
    path('collections/<int:collection_id>/edit/', views.collection_edit, name='collection_edit'),
    path('collections/<int:pk>/delete/', views.CollectionDeleteView.as_view(), name='collection_delete'),
    path('collections/<int:collection_id>/manage/', views.collection_manage, name='collection_manage'),
    path('collections/<int:collection_id>/posts/<int:post_id>/', views.collection_post_detail, name='collection_post_detail'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('settings/', views.user_settings_view, name='settings'),
    path('settings/user_delete/', views.user_delete_view, name='user_delete'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('about/', views.about_view, name='about'),
    path('logout/', views.logout_view, name='logout'),
    path('api/', include(api.router.urls)),
]
