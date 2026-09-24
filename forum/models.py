import uuid
from pathlib import Path

from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse

from md_editor.markdown import MarkdownModel
from md_editor.models import MDTextField

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


class Notification(models.Model):
    """站内通知：有人评论了我的帖子，或有人在内容里 @ 了我。

    唯一约束是「接收者 + 触发者 + 类型 + 具体对象」——同一件事重复触发
    （反复保存编辑、评论被提交多次）不会刷出一串重复通知。
    """

    KIND_COMMENT = 'comment'
    KIND_MENTION = 'mention'
    KIND_CHOICES = [
        (KIND_COMMENT, '评论了我的帖子'),
        (KIND_MENTION, '在内容里提到了我'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications')
    kind = models.CharField('类型', max_length=20, choices=KIND_CHOICES)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField('已读', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['recipient', 'actor', 'kind', 'post', 'comment'],
                name='forum_notification_unique',
            ),
        ]
        indexes = [
            # 导航栏未读数、通知列表都按「谁 + 读没读 + 时间」取
            models.Index(fields=['recipient', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f"{self.actor} -> {self.recipient}: {self.get_kind_display()}"

    def get_absolute_url(self):
        """点通知要跳到哪里：能定位到具体评论就带上锚点。"""
        if self.comment_id and self.post_id:
            return f"{reverse('post_detail', args=[self.post_id])}#comment-{self.comment_id}"
        if self.post_id:
            return reverse('post_detail', args=[self.post_id])
        return reverse('index')

    @property
    def summary(self):
        """通知文案里的动作部分。"""
        if self.kind == self.KIND_MENTION:
            return '在内容里 @ 了你'
        return '评论了你的帖子'

    @property
    def preview(self):
        """内容摘要：通知列表里用来判断「值不值得点」。"""
        if self.comment_id and self.comment is not None:
            text = (self.comment.content or '').strip()
        elif self.post_id and self.post is not None:
            text = (self.post.content or '').strip()
        else:
            return ''
        text = ' '.join(text.split())
        return text[:80] + ('…' if len(text) > 80 else '')

