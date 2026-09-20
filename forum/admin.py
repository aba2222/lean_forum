from django.contrib import admin
from .models import Item, Rating, Post, Comment, Collection, CollectionPost, Profile

# Register your models here.

admin.site.register(Item)
admin.site.register(Rating)
admin.site.register(Post)
admin.site.register(Comment)
admin.site.register(Collection)
admin.site.register(CollectionPost)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'has_avatar', 'location', 'website', 'updated_at')
    search_fields = ('user__username', 'location')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='已设置头像', boolean=True)
    def has_avatar(self, obj):
        return bool(obj.avatar)
