from .models import Post, Comment, Collection, Profile
from .avatars import normalize_avatar, delete_avatar_file

from django import forms
from django.core.files.uploadedfile import UploadedFile
import re

BIO_MAX_LENGTH = 2000

class MDEditorModelForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    class Meta:
        model = Post
        fields = ['title', 'content']
        labels = {
            'title': '标题',
            'content': '内容',
        }
    
    def clean_content(self):
        content = self.cleaned_data["content"]
        mentions = re.findall(r'@(\w+)', content)
        self.cleaned_data["mentions"] = mentions
        return content
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            instance.author = self.user
        if commit:
            instance.save()
        return instance

class CollectionForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    class Meta:
        model = Collection
        fields = ['name', 'content']
        labels = {
            'name': '合集名称',
            'content': '描述',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user and not instance.pk:
            instance.owner = self.user
        if commit:
            instance.save()
        return instance


# TODO: support @xxx
class MDEditorCommentForm(forms.ModelForm):
    def __init__(self, *args, user=None, post=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.post = post

    class Meta:
        model = Comment
        fields = ['content']
        labels = {
            'content': '内容',
        }
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            instance.author = self.user
        if self.post:
            instance.post = self.post
        if commit:
            instance.save()
        return instance


class ProfileForm(forms.ModelForm):
    """个人主页资料编辑表单：头像 + 简介 + 站点 + 所在地。

    头像走 ClearableFileInput：不选新文件 = 保持不变，勾选「清除」= 删除头像。
    clean_avatar 里把上传图统一压缩归一化后再交给 ImageField 存盘。
    """

    class Meta:
        model = Profile
        fields = ['avatar', 'content', 'website', 'location']
        labels = {
            'avatar': '头像',
            'content': '个人简介',
            'website': '个人网站',
            'location': '所在地',
        }
        help_texts = {
            'avatar': '支持 JPG / PNG / WebP，不超过 2 MB；会自动摆正方向并压缩到 512px 以内。',
            'content': f'支持 Markdown，最多 {BIO_MAX_LENGTH} 字。',
        }
        widgets = {
            'avatar': forms.ClearableFileInput(
                attrs={'accept': 'image/png,image/jpeg,image/webp', 'class': 'form-control'}
            ),
            # content 沿用 md_editor 的 MDEditorWidget（MDTextFormField 自带），
            # 保证简介的 Markdown 编辑体验与发帖/评论完全一致
            'website': forms.URLInput(
                attrs={
                    'class': 'form-control',
                    'maxlength': 200,
                    'placeholder': 'https://example.com',
                }
            ),
            'location': forms.TextInput(
                attrs={'class': 'form-control', 'maxlength': 60, 'placeholder': '例如：杭州'}
            ),
        }

    def clean_content(self):
        content = (self.cleaned_data.get('content') or '').strip()
        if len(content) > BIO_MAX_LENGTH:
            raise forms.ValidationError(f'个人简介最多 {BIO_MAX_LENGTH} 字。')
        return content

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        # None = 没换头像；False = 勾选了「清除」；
        # 其余非 UploadedFile 的值是 Django 把已有的 FieldFile 原样带回来（也不能重新编码）
        if avatar is None or avatar is False or not isinstance(avatar, UploadedFile):
            return avatar
        return normalize_avatar(avatar)

    def clean_website(self):
        return (self.cleaned_data.get('website') or '').strip()

    def clean_location(self):
        return (self.cleaned_data.get('location') or '').strip()

    def save(self, commit=True):
        # 注意：_post_clean 已经先把新文件塞进 self.instance.avatar 了，
        # 所以旧文件名必须回数据库取，不能读 instance。
        old_name = ''
        if self.instance.pk:
            old_name = (
                Profile.objects.filter(pk=self.instance.pk)
                .values_list('avatar', flat=True)
                .first()
                or ''
            )

        # 头像被清空时 FileField 收到的是 False 这个哨兵值，
        # 落库前统一收敛成「无头像」，避免把 False 写进字段
        if self.cleaned_data.get('avatar') is False:
            self.instance.avatar = None

        profile = super().save(commit=commit)

        new_name = profile.avatar.name if profile.avatar else ''
        if old_name and old_name != new_name:
            delete_avatar_file(old_name)
        return profile
