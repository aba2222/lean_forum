from .models import Post
from django import forms

class MDEditorModleForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'content']
    
    def save(self, commit=True):
        self.instance.author = self.user
        return super().save(commit)
