from .models import Post, Comment
from django import forms

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
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            instance.author = self.user
        if commit:
            instance.save()
        return instance

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
