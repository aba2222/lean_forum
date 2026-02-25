from .models import Post, Comment, Collection

from django import forms
import re

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
        fields = ['name', 'description']
        labels = {
            'name': '合集名称',
            'description': '描述',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
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
