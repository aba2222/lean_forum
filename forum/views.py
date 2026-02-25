import json, re, random
from django.db.models import F
from django.db import models as db_models
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.generic import View, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from .utils import send_group_notification

from forum.form import MDEditorCommentForm, MDEditorModelForm, CollectionForm
from forum.models import Comment, Item, Post, Rating, Collection, CollectionPost
from forum.bots_manager import manager

# Create your views here.

def index(request):
    items = Item.objects.all()
    posts = Post.objects.all().order_by('-created_at')[:5]
    return render(request, 'forum/index.html', {'items': items, 'posts' : posts})

def post_list(request):
    # IDs of posts that belong to any collection
    collected_post_ids = CollectionPost.objects.values_list('post_id', flat=True)

    # Standalone posts (not in any collection)
    standalone_posts = [
        {'type': 'post', 'obj': p, 'date': p.created_at}
        for p in Post.objects.exclude(id__in=collected_post_ids)
    ]

    # Collections as items
    collection_items = [
        {'type': 'collection', 'obj': c, 'date': c.created_at}
        for c in Collection.objects.all()
    ]

    # Merge and sort by date descending
    items = sorted(standalone_posts + collection_items, key=lambda x: x['date'], reverse=True)

    paginator = Paginator(items, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'forum/post_list.html', {
        'page_obj': page_obj,
        'now': timezone.now(),
    })

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
        post.views += 1
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

@login_required
def comment_delete_view(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    if request.method == 'POST':
        answer = request.POST.get('answer', '')
        expected = request.POST.get('expected', '')
        if answer == expected:
            post_id = comment.post.id
            comment.delete()
            return redirect('post_detail', post_id=post_id)
    a, b = random.randint(1, 9), random.randint(1, 9)
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


# ---- Collection views ----

def collection_list(request):
    collections = Collection.objects.all()
    return render(request, 'forum/collection_list.html', {'collections': collections})


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
    return render(request, 'forum/collection_detail.html', {
        'collection': collection,
        'collection_posts': posts,
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
