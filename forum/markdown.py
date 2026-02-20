from django.db import models

from mdeditor.fields import MDTextField
import markdown
import bleach

class MarkdownModel(models.Model):
    content = MDTextField(max_length=40000, default="default content")
    content_html = models.TextField(editable=False, blank=True)

    MARKDOWN_EXTENSIONS = [
        "extra",
        "codehilite",
        "toc",
        "tables",
        "fenced_code",
    ]

    allowed_tags = [
        "blockquote","b", "i", "strong", "em", "a", "p", "ul", "ol", "li",
        "code", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "img",
        "table", "thead", "tr", "th", "tbody", "td", "sup", "dt", "dd", "dl",
        "abbr", "div", "br"
    ]

    allowed_attrs = {
        "a": ["href", "title"],
        "img": ["src", "alt", "title"],
        "div" : ["class"]
    }

    ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

    class Meta:
        abstract = True

    def markdown_render(self, content):
        content_html = markdown.markdown(
                content, extensions=self.MARKDOWN_EXTENSIONS
            )
        content_html = bleach.clean(content_html, tags=self.allowed_tags, 
                               attributes=self.allowed_attrs, 
                               protocols=self.ALLOWED_PROTOCOLS)

        return content_html

    def save(self, *args, **kwargs):
        self.content_html = self.markdown_render(self.content)
        super().save(*args, **kwargs)
