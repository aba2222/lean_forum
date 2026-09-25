import re, random
from django.db.models import F, Sum
from django.db.models import Q
from django.db import models as db_models
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.generic import ListView, View, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView


from forum.api import UserRegistrationSerializer
from .geolocation import refresh_profile_region
from .utils import send_group_notification
from forum.form import MDEditorCommentForm, MDEditorModelForm, CollectionForm, ProfileForm
from forum.models import Comment, Item, Post, Rating, Collection, CollectionPost, Profile
from forum.bots_manager import manager

# Create your views here.

def index(request):
    items = Item.objects.all()
    posts = Post.objects.order_by('-created_at')[:6]
    post_count = Post.objects.count()
    return render(request, 'forum/index.html', {'items': items, 'posts' : posts, 'post_count': post_count})

class PostListView(ListView):
    model = Post
    template_name = 'forum/post_list.html'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        return context

    def get_queryset(self):
       query = self.request.GET.get("q", "").strip()
       if not query:
           return Post.objects.all()
       return Post.objects.filter(
           Q(title__icontains=query) | Q(content__icontains=query)
       )

@login_required
def rate_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.method == 'POST':
        try:
            score = int(request.POST.get('score', ''))
        except (TypeError, ValueError):
            messages.error(request, '评分必须是 1-5 之间的整数。')
            return redirect('rate_item', item_id=item.id)
        if not 1 <= score <= 5:
            messages.error(request, '评分必须在 1-5 之间。')
            return redirect('rate_item', item_id=item.id)
        Rating.objects.update_or_create(
            user=request.user,
            item=item,
            defaults={'score': score}
        )
        return redirect('index')

    return render(request, 'forum/rate_item.html', {'name': item.name,'description': item.content_html})

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
        Post.objects.filter(id=post_id).update(views=F('views') + 1)
        post.refresh_from_db(fields=['views'])
        forms = None
        if request.user.is_authenticated:
            forms = MDEditorCommentForm(user=request.user, post=post)
        
        comments = post.comments.all().order_by('created_at')
        paginator = Paginator(comments, 8)
        page_obj = paginator.get_page(request.GET.get('page', 1))

        return render(request, 'forum/post_detail.html', {'post': post,
                                                          'comments': page_obj,
                                                          'page_obj': page_obj,
                                                          'total_comments': paginator.count,
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

        if not username or not (2 <= len(username) <= 20):
            messages.error(request, '用户名长度需在 2-20 个字符之间')
            return redirect('register')

        if not re.match(r'^[\w\u4e00-\u9fff]+$', username):
            messages.error(request, '用户名只能包含字母、数字、下划线或中文')
            return redirect('register')

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

    def post(self, request, *args, **kwargs):
        confirm_title = request.POST.get('confirm_title', '')
        self.object = self.get_object()
        if confirm_title != self.object.title:
            messages.error(request, '确认标题不匹配，删除已取消。')
            return redirect('post_detail', post_id=self.object.pk)
        return super().post(request, *args, **kwargs)

@login_required
def comment_delete_view(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    if request.method == 'POST':
        answer = request.POST.get('answer', '')
        expected = request.session.get('comment_delete_expected')
        if expected is not None and answer == str(expected):
            request.session.pop('comment_delete_expected', None)
            post_id = comment.post.id
            comment.delete()
            return redirect('post_detail', post_id=post_id)
        messages.error(request, '验证答案不正确，删除已取消。')
        return redirect('post_detail', post_id=comment.post.id)
    a, b = random.randint(1, 9), random.randint(1, 9)
    request.session['comment_delete_expected'] = a + b
    return render(request, 'forum/comment_check_delete.html', {
        'comment': comment, 'a': a, 'b': b, 'answer': a + b,
    })

@login_required
def post_edit_view(request, post_id):
    post = get_object_or_404(Post, id=post_id, author=request.user)
    form = MDEditorModelForm(request.POST or None, instance=post, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('post_detail', post_id=post.id)
    return render(request, 'forum/post_edit.html', {'form': form, 'post': post})

@login_required
def comment_edit_view(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    form = MDEditorCommentForm(request.POST or None, instance=comment, user=request.user, post=comment.post)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('post_detail', post_id=comment.post.id)
    return render(request, 'forum/comment_edit.html', {'form': form, 'comment': comment})

@login_required
def user_settings_view(request):
    webpush = {"group": "webpush_new_posts" } 
    return render(request, "forum/user_settings.html",  {"webpush" : webpush})

@login_required
def user_delete_view(request):
    if request.method == 'POST':
        password = request.POST.get('password')
        username = request.POST.get('username', '')
        confirm_text = request.POST.get('confirm_text', '')
        user = authenticate(request, username=request.user.username, password=password)
        if user is not None and username == request.user.username and confirm_text == '我要删除账户':
            logout(request)
            user.delete()
            return redirect('index')
        else:
            messages.error(request, '账户信息不匹配，删除已取消。')
            return redirect('settings')

@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')

def about_view(request):
    return render(request, "forum/about.html")


# ---- Collection views ----

def collection_list(request):
    collections = Collection.objects.select_related('owner').all()
    paginator = Paginator(collections, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'forum/collection_list.html', {
        'collections': page_obj,
        'page_obj': page_obj,
    })


@login_required
def collection_create(request):
    form = CollectionForm(user=request.user)
    if request.method == 'POST':
        form = CollectionForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('collection_list')
    return render(request, 'forum/collection_form.html', {'form': form})


def collection_detail(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    posts = collection.collection_posts.select_related('post', 'post__author').all()
    paginator = Paginator(posts, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'forum/collection_detail.html', {
        'collection': collection,
        'collection_posts': page_obj,
        'page_obj': page_obj,
    })


@login_required
def collection_edit(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    form = CollectionForm(instance=collection, user=request.user)
    if request.method == 'POST':
        form = CollectionForm(request.POST, instance=collection, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('collection_detail', collection_id=collection.id)
    return render(request, 'forum/collection_form.html', {'form': form, 'title': '编辑合集'})


class CollectionDeleteView(LoginRequiredMixin, DeleteView):
    login_url = "login"
    model = Collection
    template_name = 'forum/collection_check_delete.html'
    success_url = reverse_lazy("collection_list")

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)

    def post(self, request, *args, **kwargs):
        confirm_name = request.POST.get('confirm_name', '')
        self.object = self.get_object()
        if confirm_name != self.object.name:
            messages.error(request, '确认名称不匹配，删除已取消。')
            return redirect('collection_detail', collection_id=self.object.pk)
        return super().post(request, *args, **kwargs)


@login_required
def collection_manage(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        cp_id = request.POST.get('cp_id')

        if action == 'remove' and cp_id:
            CollectionPost.objects.filter(id=cp_id, collection=collection).delete()

        elif action == 'move_up' and cp_id:
            cp = get_object_or_404(CollectionPost, id=cp_id, collection=collection)
            prev = collection.collection_posts.filter(order__lt=cp.order).last()
            if prev:
                prev.order, cp.order = cp.order, prev.order
                prev.save()
                cp.save()

        elif action == 'move_down' and cp_id:
            cp = get_object_or_404(CollectionPost, id=cp_id, collection=collection)
            nxt = collection.collection_posts.filter(order__gt=cp.order).first()
            if nxt:
                nxt.order, cp.order = cp.order, nxt.order
                nxt.save()
                cp.save()

        elif action == 'reorder':
            order_ids = request.POST.get('order', '')
            if order_ids:
                for i, cp_id_str in enumerate(order_ids.split(',')):
                    CollectionPost.objects.filter(id=int(cp_id_str), collection=collection).update(order=i)
            return JsonResponse({'ok': True})

        elif action == 'add':
            post_ids = request.POST.getlist('post_id')
            for pid in post_ids:
                post = get_object_or_404(Post, id=pid, author=request.user)
                if not CollectionPost.objects.filter(collection=collection, post=post).exists():
                    max_order = collection.collection_posts.aggregate(db_models.Max('order'))['order__max'] or 0
                    CollectionPost.objects.create(collection=collection, post=post, order=max_order + 1)

        return redirect('collection_manage', collection_id=collection.id)

    collection_posts = collection.collection_posts.select_related('post').all()
    # Available posts: authored by user and not already in this collection
    existing_ids = collection.collection_posts.values_list('post_id', flat=True)
    available_posts = Post.objects.filter(author=request.user).exclude(id__in=existing_ids)

    return render(request, 'forum/collection_manage.html', {
        'collection': collection,
        'collection_posts': collection_posts,
        'available_posts': available_posts,
    })


def collection_post_detail(request, collection_id, post_id):
    collection = get_object_or_404(Collection, id=collection_id)
    current_cp = get_object_or_404(CollectionPost, collection=collection, post_id=post_id)
    post = current_cp.post

    prev_cp = collection.collection_posts.filter(order__lt=current_cp.order).last()
    next_cp = collection.collection_posts.filter(order__gt=current_cp.order).first()

    forms = None
    if request.user.is_authenticated:
        forms = MDEditorCommentForm(user=request.user, post=post)

    if request.method == 'POST' and request.user.is_authenticated:
        forms = MDEditorCommentForm(request.POST, user=request.user, post=post)
        if forms.is_valid():
            forms.save()
        return redirect('collection_post_detail', collection_id=collection.id, post_id=post.id)

    comments = post.comments.all().order_by('created_at')
    paginator = Paginator(comments, 8)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'forum/post_detail.html', {
        'post': post,
        'collection': collection,
        'collection_posts_all': collection.collection_posts.select_related('post').all(),
        'prev_post': prev_cp.post if prev_cp else None,
        'next_post': next_cp.post if next_cp else None,
        'comments': page_obj,
        'page_obj': page_obj,
        'total_comments': paginator.count,
        'forms': forms,
        'can_delete': (post.author == request.user),
    })


@login_required
def post_add_to_collection(request, post_id):
    post = get_object_or_404(Post, id=post_id, author=request.user)
    collections = request.user.collections.all()

    if request.method == 'POST':
        collection_id = request.POST.get('collection_id')
        collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
        if not CollectionPost.objects.filter(collection=collection, post=post).exists():
            max_order = collection.collection_posts.aggregate(db_models.Max('order'))['order__max'] or 0
            CollectionPost.objects.create(collection=collection, post=post, order=max_order + 1)
        return redirect('post_detail', post_id=post.id)

    return render(request, 'forum/post_add_to_collection.html', {
        'post': post,
        'collections': collections,
    })

class UserRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
              "message": "User registered successfully"
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---- Profile / 个人主页 ----

PROFILE_TABS = ('posts', 'comments', 'collections')
PROFILE_PAGE_SIZE = 10


def profile_view(request, username):
    """公开的个人主页：头像、简介、统计，以及帖子/评论/合集三个分页列表。"""
    profile_user = get_object_or_404(User, username=username)
    profile, _ = Profile.objects.get_or_create(user=profile_user)

    posts = Post.objects.filter(author=profile_user).order_by('-created_at')
    comments = (
        Comment.objects.filter(author=profile_user)
        .select_related('post')
        .order_by('-created_at')
    )
    collections = Collection.objects.filter(owner=profile_user).order_by('-created_at')

    tab = request.GET.get('tab', 'posts')
    if tab not in PROFILE_TABS:
        tab = 'posts'

    active_qs = {'posts': posts, 'comments': comments, 'collections': collections}[tab]
    paginator = Paginator(active_qs, PROFILE_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'forum/profile.html', {
        'profile': profile,
        'profile_user': profile_user,
        'tab': tab,
        'page_obj': page_obj,
        'stats': {
            'posts': posts.count(),
            'comments': comments.count(),
            'collections': collections.count(),
            'views': posts.aggregate(total=Sum('views'))['total'] or 0,
        },
        'is_self': request.user.is_authenticated and request.user.pk == profile_user.pk,
    })


@login_required
def profile_edit_view(request):
    """编辑自己的资料：头像、简介、个人网站。

    归属地不在这里填 —— 它由登录时的 IP 自动算出（见 forum/geolocation.py）。
    保存资料时顺手强制重算一次，用户换了网络再改资料就能立刻看到更新。
    """
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save()
            refresh_profile_region(profile, request, force=True)
            messages.success(request, '资料已更新。')
            return redirect('profile', username=request.user.username)
        messages.error(request, '资料保存失败，请检查下面的提示。')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'forum/profile_edit.html', {'form': form, 'profile': profile})
