from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.generic import ListView, View, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
import markdown
import bleach
from .utils import send_group_notification

from forum.form import MDEditorCommentForm, MDEditorModelForm
from forum.models import Item, Post, Rating
from forum.bots_manager import manager

# Create your views here.

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

def index(request):
    items = Item.objects.all()
    posts = Post.objects.all().order_by('-created_at')[:5]
    return render(request, 'forum/index.html', {'items': items, 'posts' : posts})

class PostListView(ListView):
    paginate_by = 20
    model = Post
    ordering = ["-created_at"]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        return context

@login_required
def rate_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.method == 'POST':
        score = int(request.POST.get('score'))
        Rating.objects.update_or_create(
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
            post = forms.save()

            mentions = forms.cleaned_data.get("mentions", [])
            for mention in mentions:
                manager.at_bot(mention, post)

            send_group_notification("webpush_new_posts", "新帖子发布了，快去看看吧！", "https://lforum.dpdns.org/posts/")

            return redirect('post_list')
        else:
            print(forms.errors)
    
    return render(request, 'forum/post_create.html', {'form': forms})

class PostDetailView(View):
    def get(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)
        forms = None
        if request.user.is_authenticated:
            forms = MDEditorCommentForm(user=request.user, post=post)
        
        comments = post.comments.all().order_by('created_at')

        post.content = markdown.markdown(
            post.content, extensions=['extra', 'codehilite', 'toc']
        )
        post.content = bleach.clean(post.content, tags=allowed_tags, attributes=allowed_attrs, protocols=ALLOWED_PROTOCOLS)

        for comment in comments:
            comment.content = markdown.markdown(
                comment.content, extensions=['extra', 'codehilite', 'toc']
            )
            comment.content = bleach.clean(comment.content, tags=allowed_tags, attributes=allowed_attrs, protocols=ALLOWED_PROTOCOLS)
        
        return render(request, 'forum/post_detail.html', {'post': post, 
                                                          'comments': comments,
                                                          'forms' : forms, 
                                                          'can_delete' : (post.author == request.user)})

    def post(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)
        if request.user.is_authenticated:
            forms = MDEditorCommentForm(request.POST,  user=request.user, post=post)
            forms.user = request.user
            forms.post = post
            if forms.is_valid():
                forms.save()
            else:
                print(forms.errors)
        return redirect('post_detail', post_id=post.id)

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

class PostDeleteView(LoginRequiredMixin, DeleteView):
    login_url = "login"
    model = Post
    template_name_suffix = '_check_delete'
    success_url = reverse_lazy("post_list")

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(author=self.request.user)

@login_required
def user_settings_view(request):
    webpush = {"group": "webpush_new_posts" } 
    return render(request, "forum/user_settings.html",  {"webpush" : webpush})

@login_required
def user_delete_view(request):
    if request.method == 'POST':
        password = request.POST.get('password')
        user = authenticate(request, username=request.user.username, password=password)
        if user is not None:
            logout(request)
            user.delete()
            return redirect('index')
        else:
            messages.error(request, '密码错误，请重新输入')
            return redirect('settings')

def logout_view(request):
    logout(request)
    return redirect('login')

def about_view(request):
    return render(request, "forum/about.html")
