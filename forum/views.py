from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required

from forum.models import Comment, Item, Post, Rating

# Create your views here.

def index(request):
    items = Item.objects.all()
    posts = Post.objects.all().order_by('-created_at')[:5]
    return render(request, 'forum/index.html', {'items': items, 'posts' : posts})

def post_list(request):
    posts = Post.objects.all().order_by('-created_at')
    return render(request, 'forum/post_list.html', {'posts': posts})

@login_required
def rate_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.method == 'POST':
        score = int(request.POST.get('score'))
        rating, created = Rating.objects.update_or_create(
            user=request.user,
            item=item,
            defaults={'score': score}
        )
        return redirect('index')
    return render(request, 'forum/rate_item.html', {'item': item})

@login_required
def post_create(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        Post.objects.create(author=request.user, title=title, content=content)
        return redirect('post_list')
    return render(request, 'forum/post_create.html')

def post_detail(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        if request.user.is_authenticated:
            content = request.POST.get('content')
            Comment.objects.create(post=post, author=request.user, content=content)
            return redirect('post_detail', post_id=post.id)
    comments = post.comment_set.all().order_by('created_at')
    return render(request, 'forum/post_detail.html', {'post': post, 'comments': comments})
