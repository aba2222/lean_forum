from pyexpat.errors import messages
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib import messages

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

def login_view(request):
    if request.method == 'POST':
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            # 返回一个“无效登录”错误消息
            messages.error(request, '用户名或密码错误')
            return redirect('login')  # 重定向回登录页面，保持表单和错误信息
    else:
        return render(request, 'forum/login.html')  # GET 请求时返回登录页面

def register_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']

        if password != confirm_password:
            messages.error(request, '密码不一致，请重新输入')
            return redirect('register')

        try:
            user = User.objects.create_user(username=username, password=password)
            user.save()

            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)

            messages.success(request, '注册成功！')
            return redirect('index')
        except Exception as e:
            messages.error(request, f'注册失败：{str(e)}')
            return redirect('register')

    return render(request, 'forum/register.html')

