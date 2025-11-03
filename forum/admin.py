from django.contrib import admin
from .models import Item, Rating, Post, Comment

# Register your models here.

admin.site.register(Item)
admin.site.register(Rating)
admin.site.register(Post)
admin.site.register(Comment)
