from django.db import models
from django.contrib.auth.models import User

from .markdown import MarkdownModel

import markdown
import bleach

# Create your models here.

class Item(MarkdownModel):
    name = models.CharField(max_length=50, unique=True)

    def average_rating(self):
        avg_rating = self.rating_set.aggregate(models.Avg('score'))['score__avg']
        return avg_rating if avg_rating is not None else 0 

    def __str__(self):
        return f"{self.name} (avg: {self.average_rating():.1f})"
    
class Rating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)

    class Meta:
        unique_together = ('user', 'item')

class Post(MarkdownModel):
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    views = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.title} by {self.author}"
    
    class Meta:
        ordering = ['-created_at'] 

class Comment(MarkdownModel):
    post = models.ForeignKey(Post, related_name="comments", on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author} comment {self.post}"


class Collection(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collections')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    description_html = models.TextField(editable=False, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.description:
            html = markdown.markdown(self.description, extensions=MarkdownModel.MARKDOWN_EXTENSIONS)
            self.description_html = bleach.clean(
                html,
                tags=MarkdownModel.allowed_tags,
                attributes=MarkdownModel.allowed_attrs,
                protocols=MarkdownModel.ALLOWED_PROTOCOLS,
            )
        else:
            self.description_html = ''
        super().save(*args, **kwargs)


class CollectionPost(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='collection_posts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='collection_entries')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ('collection', 'post')

    def __str__(self):
        return f"{self.collection.name} - {self.post.title}"
