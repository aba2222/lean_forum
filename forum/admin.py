from django.contrib import admin
from .models import Item, Rating, Post, Comment, Collection, CollectionPost

# Register your models here.

admin.site.register(Item)
admin.site.register(Rating)
admin.site.register(Post)
admin.site.register(Comment)
admin.site.register(Collection)
admin.site.register(CollectionPost)
