import uuid
from pathlib import Path

from django.db import models
from django.contrib.auth.models import User

from md_editor.markdown import MarkdownModel
from md_editor.models import MDTextField

from .covers import cover_upload_to

# Create your models here.


def avatar_upload_to(instance, filename):
    """头像落盘路径：uploads/avatars/u<user_id>/<uuid><ext>。

    文件名由 uuid 生成，避免用户上传的文件名互相覆盖或带出原始路径。
    """
    suffix = Path(filename).suffix.lower()
    if suffix == '.jpeg':
        suffix = '.jpg'
    if suffix not in ('.jpg', '.png', '.webp'):
        suffix = '.jpg'
    return f"avatars/u{instance.user_id}/{uuid.uuid4().hex}{suffix}"


class Profile(MarkdownModel):
    """用户个人主页资料，与 User 一对一。

    简介复用 MarkdownModel：content 存原文，content_html 在 save() 时
    经 markdown-it + bleach 白名单渲染，个人主页展示的简介同样走这条安全管线。
    头像为空时前端回退为「用户名首字 + 稳定底色」的字母头像（见 forum/avatars.py）。
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField('头像', upload_to=avatar_upload_to, blank=True, null=True)
    #: 个人主页顶部的背景图；没上传时前端用按用户名生成的渐变兜底
    cover = models.ImageField('主页背景', upload_to=cover_upload_to, blank=True, null=True)
    content = MDTextField(max_length=200, blank=True, verbose_name='个人简介')
    website = models.URLField('个人网站', max_length=200, blank=True)
    location = models.CharField('所在地', max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} 的个人资料"


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
