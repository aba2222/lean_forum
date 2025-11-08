from .models import Post, Comment
from django import forms

class MDEditorModleForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'content']
    
    def save(self, commit=True):
        self.instance.author = self.user
        return super().save(commit)

class MDEditorCommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
    
    def save(self, commit=True):
        self.instance.author = self.user
        self.instance.post = self.post
        return super().save(commit)
