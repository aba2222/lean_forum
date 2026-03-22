from django.db import models
from django.contrib.auth.models import User
from django_activitypub.models import LocalActor, Note
from django.urls import reverse

from .markdown import MarkdownModel

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

    def get_absolute_url(self):
        return reverse('post_detail', kwargs={'post_id': self.id})

    def publish(self, base_uri):
        actor = LocalActor.objects.get(user=self.author)
        Note.objects.upsert(
            base_uri=base_uri,
            local_actor=actor,
            content=self.content_html,
            content_url=f'{base_uri}{self.get_absolute_url()}'
        )
    
    def delete(self, base_uri, *args, **kwargs):
        Note.objects.delete_local(
            base_uri=base_uri,
            content_url=f'{base_uri}{self.get_absolute_url()}',
        )
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.title} by {self.author}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        #TODO: base_uri should be dynamic
        self.publish(base_uri='http://localhost:8000')
    
    class Meta:
        ordering = ['-created_at'] 

class Comment(MarkdownModel):
    post = models.ForeignKey(Post, related_name="comments", on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author} comment {self.post}"


class Collection(MarkdownModel):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collections')
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class CollectionPost(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='collection_posts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='collection_entries')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ('collection', 'post')

    def __str__(self):
        return f"{self.collection.name} - {self.post.title}"
