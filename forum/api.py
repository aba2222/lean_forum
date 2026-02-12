from .models import Post, Comment
from rest_framework import routers, serializers, viewsets

# Serializers define the API representation.
class CommentSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.username")

    class Meta:
        model = Comment
        fields = ["id", "author", "content", "created_at"]

class PostListSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.username")

    class Meta:
        model = Post
        fields = ["id", "author", "title", "content", "created_at"]

class PostDetailSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.username")
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "title",
            "content",
            "created_at",
            "comments",
        ]

# ViewSets define the view behavior.
class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()

    def get_queryset(self):
        return Post.objects.select_related("author").prefetch_related("comments__author")

    def get_serializer_class(self):
        if self.action == "list":
            return PostListSerializer
        return PostDetailSerializer


# Routers provide a way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register(r"posts", PostViewSet)

