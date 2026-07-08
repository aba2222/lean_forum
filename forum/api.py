from .models import Post, Comment
from rest_framework import routers, serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "author", "author_name", "content", "created_at"]
        read_only_fields = ["author", "author_name", "created_at"]


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ["content"]


class PostListSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = Post
        fields = ["id", "author", "author_name", "title", "created_at"]
        read_only_fields = ["author", "author_name", "created_at"]


class PostDetailSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.username", read_only=True)
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "author_name",
            "title",
            "content",
            "created_at",
            "comments",
        ]
        read_only_fields = ["author", "author_name", "created_at", "comments"]


class PostCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ["title", "content"]


class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return Post.objects.select_related("author").prefetch_related("comments__author")

    def get_serializer_class(self):
        if self.action == "list":
            return PostListSerializer
        if self.action == "create":
            return PostCreateSerializer
        return PostDetailSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def destroy(self, request, *args, **kwargs):
        post = self.get_object()
        if not request.user.is_authenticated or post.author != request.user:
            raise AuthenticationFailed("Only the author can delete this post.")
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="comments")
    def comments(self, request, pk=None):
        post = self.get_object()
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(author=request.user, post=post)
        return Response(CommentSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)


router = routers.DefaultRouter()
router.register(r"posts", PostViewSet)

