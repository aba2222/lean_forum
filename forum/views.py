from django.utils import timezone
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.generic import ListView, View, UpdateView
import markdown

from forum.form import MDEditorCommentForm, MDEditorModelForm
from forum.models import Item, Post, Rating

# Create your views here.

def index(request):
    items = Item.objects.all()
    posts = Post.objects.all().order_by('-created_at')[:5]
    return render(request, 'forum/index.html', {'items': items, 'posts' : posts})

class PostListView(ListView):
    paginate_by = 20
    model = Post
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        return context

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
    item.description = markdown.markdown(
        item.description, extensions=["extra", "codehilite", "toc", "tables", "fenced_code"]
    )
    return render(request, 'forum/rate_item.html', {'name': item.name,'description': item.description})

@login_required
def post_create(request):
    forms = MDEditorModelForm(user=request.user)
    if request.method == 'POST':
        forms = MDEditorModelForm(request.POST, user=request.user)
        if forms.is_valid():
            forms.save()
            return redirect('post_list')
        else:
            print(forms.errors)
    
    return render(request, 'forum/post_create.html', {'form': forms})

def post_detail(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    forms = None
    if request.user.is_authenticated:
        forms = MDEditorCommentForm(user=request.user, post=post)
    if request.method == 'POST':
        if request.user.is_authenticated:
            forms = MDEditorCommentForm(request.POST,  user=request.user, post=post)
            forms.user = request.user
            forms.post = post
            if forms.is_valid():
                forms.save()
                return redirect('post_detail', post_id=post.id)
            else:
                print(forms.errors)
    comments = post.comment_set.all().order_by('created_at')

    post.content = markdown.markdown(
        post.content, extensions=['extra', 'codehilite', 'toc']
    )
    for comment in comments:
        comment.content = markdown.markdown(
            comment.content, extensions=['extra', 'codehilite', 'toc']
        )
    return render(request, 'forum/post_detail.html', {'post': post, 'comments': comments, 'forms' : forms})

class LoginView(View):
    def get(self, request):
        return render(request, 'forum/login.html')  # GET 请求时返回登录页面

    def post(self,request):
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            # 返回一个“无效登录”错误消息
            messages.error(request, '用户名或密码错误')
            return redirect('login')  # 重定向回登录页面，保持表单和错误信息

class RegisterView(View):
    def get(self, request):
        return render(request, 'forum/register.html')
    
    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

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

def logout_view(request):
    logout(request)
    return redirect('login')

def about_view(request):
    return render(request, "forum/about.html")
