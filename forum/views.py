import logging
import re, random
from django.db.models import Avg, Count, F, Q, Sum
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
from .utils import send_group_notification
from forum.form import MDEditorCommentForm, MDEditorModelForm, CollectionForm, ProfileForm
from forum.models import Comment, Item, Post, Rating, Collection, CollectionPost, Profile
from forum.bots_manager import manager

logger = logging.getLogger(__name__)

# Create your views here.

def index(request):
    items = Item.objects.annotate(
        avg_score=Avg('rating__score'),
        rating_count=Count('rating'),
    )
    posts = Post.objects.select_related('author').order_by('-created_at')[:6]
    post_count = Post.objects.count()
    return render(request, 'forum/index.html', {
        'items': items,
        'posts': posts,
        'post_count': post_count,
        'star_range': range(1, 6),
    })


class PostListView(ListView):
    model = Post
    template_name = 'forum/post_list.html'
    paginate_by = 20
    context_object_name = 'posts'

    def get_queryset(self):
        qs = Post.objects.select_related('author').order_by('-created_at')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(content__icontains=q)
                | Q(author__username__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["q"] = self.request.GET.get('q', '').strip()
        context["post_count"] = self.get_queryset().count()
        return context


@login_required
def rate_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    user_rating = None
    if request.user.is_authenticated:
        user_rating = Rating.objects.filter(user=request.user, item=item).first()

    if request.method == 'POST':
        try:
            score = int(request.POST.get('score', ''))
        except (TypeError, ValueError):
            messages.error(request, '评分必须是 1-5 之间的整数。')
            return redirect('rate_item', item_id=item.id)
        if not 1 <= score <= 5:
            messages.error(request, '评分必须在 1-5 之间。')
            return redirect('rate_item', item_id=item.id)
        _obj, created = Rating.objects.update_or_create(
            user=request.user,
            item=item,
            defaults={'score': score}
        )
        if created:
            messages.success(request, f'已为「{item.name}」打 {score} 星。')
        else:
            messages.success(request, f'已更新对「{item.name}」的评分为 {score} 星。')
        return redirect('index')

    avg = item.average_rating()
    rating_count = item.rating_set.count()
    # 模板里同时要用到 item.name 与正文，整对象一起传
    return render(request, 'forum/rate_item.html', {
        'item': item,
        'average_rating': avg,
        'rating_count': rating_count,
        'user_rating': user_rating.score if user_rating else None,
        'star_range': range(1, 6),
    })


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

            try:
                send_group_notification("webpush_new_posts", "新帖子发布了，快去看看吧！", "https://lforum.dpdns.org/posts/")
            except Exception:
                logger.exception("发送 webpush 通知失败")

            messages.success(request, f'帖子「{post.title}」发布成功！')
            return redirect('post_list')
        else:
            logger.warning("post_create 表单校验失败: user=%s errors=%s", request.user.id, forms.errors)
            messages.error(request, '帖子内容校验失败，请检查必填项后重试。')
            for field, errs in forms.errors.items():
                for err in errs:
                    messages.warning(request, f'[{field}] {err}')

    return render(request, 'forum/post_create.html', {'form': forms})


def _post_detail_context(post, request, comment_form=None, collection=None, prev_post=None, next_post=None, all_cps=None):
    Post.objects.filter(id=post.id).update(views=F('views') + 1)
    post.refresh_from_db(fields=['views'])
    forms = comment_form
    if forms is None and request.user.is_authenticated:
        forms = MDEditorCommentForm(user=request.user, post=post)

    comments = post.comments.select_related('author').order_by('created_at')
    paginator = Paginator(comments, 8)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return {
        'post': post,
        'collection': collection,
        'collection_posts_all': all_cps,
        'prev_post': prev_post,
        'next_post': next_post,
        'comments': page_obj,
        'page_obj': page_obj,
        'total_comments': paginator.count,
        'forms': forms,
        'can_delete': (post.author == request.user),
    }


class PostDetailView(View):
    def get(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)
        ctx = _post_detail_context(post, request)
        return render(request, 'forum/post_detail.html', ctx)

    def post(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)
        if not request.user.is_authenticated:
            messages.warning(request, '请先登录后再发表评论。')
            return redirect('login')
        forms = MDEditorCommentForm(request.POST, user=request.user, post=post)
        forms.user = request.user
        forms.post = post
        if forms.is_valid():
            forms.save()
            messages.success(request, '评论发布成功！')
            return redirect('post_detail', post_id=post.id)
        # 校验失败：回显已有内容 + messages，避免用户丢失输入
        logger.warning(
            "PostDetailView 评论表单校验失败: post=%s user=%s errors=%s",
            post_id, request.user.id, forms.errors,
        )
        messages.error(request, '评论内容校验失败，请修正后重新提交。您已输入的内容已保留。')
        for field, errs in forms.errors.items():
            for err in errs:
                messages.warning(request, f'[{field}] {err}')
        ctx = _post_detail_context(post, request, comment_form=forms)
        return render(request, 'forum/post_detail.html', ctx)


class LoginView(View):
    def get(self, request):
        return render(request, 'forum/login.html')

    def post(self, request):
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.info(request, f'欢迎回来，{user.username}！')
            return redirect('index')
        else:
            messages.error(request, '用户名或密码错误')
            return redirect('login')


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

            messages.success(request, '注册成功！欢迎加入 Lean Forum')
            return redirect('index')
        except Exception as e:
            logger.exception("注册失败 user=%s", username)
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
        title = self.object.title
        result = super().post(request, *args, **kwargs)
        messages.success(request, f'帖子「{title}」已成功删除。')
        return result


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
            messages.success(request, '评论已删除。')
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
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, f'帖子「{post.title}」已更新。')
            return redirect('post_detail', post_id=post.id)
        logger.warning(
            "post_edit_view 表单校验失败: post=%s user=%s errors=%s",
            post_id, request.user.id, form.errors,
        )
        messages.error(request, '修改失败，请检查必填项。已保留您当前的输入。')
    return render(request, 'forum/post_edit.html', {'form': form, 'post': post})


@login_required
def comment_edit_view(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    form = MDEditorCommentForm(request.POST or None, instance=comment, user=request.user, post=comment.post)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, '评论已更新。')
            return redirect('post_detail', post_id=comment.post.id)
        logger.warning(
            "comment_edit_view 表单校验失败: comment=%s user=%s errors=%s",
            comment_id, request.user.id, form.errors,
        )
        messages.error(request, '评论修改失败，请检查输入内容。')
    return render(request, 'forum/comment_edit.html', {'form': form, 'comment': comment})


@login_required
def user_settings_view(request):
    webpush = {"group": "webpush_new_posts"}
    return render(request, "forum/user_settings.html", {"webpush": webpush})


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
            messages.info(request, '账户已成功删除，再见！')
            return redirect('index')
        else:
            messages.error(request, '账户信息不匹配，删除已取消。')
            return redirect('settings')


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, '您已安全登出。')
    return redirect('login')


def about_view(request):
    return render(request, "forum/about.html")


def custom_404_view(request, exception=None):
    return render(request, "404.html", status=404)


def custom_500_view(request, exception=None):
    return render(request, "500.html", status=500)


# ---- Collection views ----

def collection_list(request):
    collections = Collection.objects.select_related('owner').annotate(
        post_count=Count('collection_posts'),
    ).order_by('-created_at')
    paginator = Paginator(collections, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'forum/collection_list.html', {
        'collections': page_obj,
        'page_obj': page_obj,
        'collection_count': paginator.count,
    })


@login_required
def collection_create(request):
    form = CollectionForm(user=request.user)
    if request.method == 'POST':
        form = CollectionForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'合集「{form.instance.name}」已创建。')
            return redirect('collection_list')
        logger.warning(
            "collection_create 表单校验失败: user=%s errors=%s",
            request.user.id, form.errors,
        )
        messages.error(request, '合集创建失败，请检查输入内容。')
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
        'post_count': paginator.count,
    })


@login_required
def collection_edit(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)
    form = CollectionForm(instance=collection, user=request.user)
    if request.method == 'POST':
        form = CollectionForm(request.POST, instance=collection, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'合集「{collection.name}」已更新。')
            return redirect('collection_detail', collection_id=collection.id)
        logger.warning(
            "collection_edit 表单校验失败: collection=%s errors=%s",
            collection_id, form.errors,
        )
        messages.error(request, '合集修改失败，请检查输入内容。')
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
        name = self.object.name
        result = super().post(request, *args, **kwargs)
        messages.success(request, f'合集「{name}」已成功删除。')
        return result


@login_required
def collection_manage(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id, owner=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        cp_id = request.POST.get('cp_id')

        if action == 'remove' and cp_id:
            CollectionPost.objects.filter(id=cp_id, collection=collection).delete()
            messages.info(request, '已将帖子从合集中移除。')

        elif action == 'move_up' and cp_id:
            cp = get_object_or_404(CollectionPost, id=cp_id, collection=collection)
            prev = collection.collection_posts.filter(order__lt=cp.order).last()
            if prev:
                prev.order, cp.order = cp.order, prev.order
                prev.save()
                cp.save()
                messages.info(request, '已上移顺序。')

        elif action == 'move_down' and cp_id:
            cp = get_object_or_404(CollectionPost, id=cp_id, collection=collection)
            nxt = collection.collection_posts.filter(order__gt=cp.order).first()
            if nxt:
                nxt.order, cp.order = cp.order, nxt.order
                nxt.save()
                cp.save()
                messages.info(request, '已下移顺序。')

        elif action == 'reorder':
            order_ids = request.POST.get('order', '')
            if order_ids:
                for i, cp_id_str in enumerate(order_ids.split(',')):
                    CollectionPost.objects.filter(id=int(cp_id_str), collection=collection).update(order=i)
            return JsonResponse({'ok': True})

        elif action == 'add':
            post_ids = request.POST.getlist('post_id')
            added = 0
            for pid in post_ids:
                post = get_object_or_404(Post, id=pid, author=request.user)
                if not CollectionPost.objects.filter(collection=collection, post=post).exists():
                    max_order = collection.collection_posts.aggregate(db_models.Max('order'))['order__max'] or 0
                    CollectionPost.objects.create(collection=collection, post=post, order=max_order + 1)
                    added += 1
            if added:
                messages.success(request, f'已添加 {added} 篇帖子到合集。')
            else:
                messages.info(request, '没有新帖子被添加。')

        return redirect('collection_manage', collection_id=collection.id)

    collection_posts = collection.collection_posts.select_related('post').all()
    existing_ids = collection.collection_posts.values_list('post_id', flat=True)
    available_posts = Post.objects.filter(author=request.user).exclude(id__in=existing_ids).order_by('-created_at')

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
    all_cps = collection.collection_posts.select_related('post').all()

    forms = None
    if request.user.is_authenticated:
        forms = MDEditorCommentForm(user=request.user, post=post)

    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.warning(request, '请先登录后再发表评论。')
            return redirect('login')
        forms = MDEditorCommentForm(request.POST, user=request.user, post=post)
        if forms.is_valid():
            forms.save()
            messages.success(request, '评论发布成功！')
            return redirect('collection_post_detail', collection_id=collection.id, post_id=post.id)
        logger.warning(
            "collection_post_detail 评论表单校验失败: collection=%s post=%s errors=%s",
            collection_id, post_id, forms.errors,
        )
        messages.error(request, '评论内容校验失败，请修正后重新提交。您已输入的内容已保留。')
        for field, errs in forms.errors.items():
            for err in errs:
                messages.warning(request, f'[{field}] {err}')
        # 失败时走 render 回显
        ctx = _post_detail_context(
            post, request,
            comment_form=forms,
            collection=collection,
            prev_post=prev_cp.post if prev_cp else None,
            next_post=next_cp.post if next_cp else None,
            all_cps=all_cps,
        )
        return render(request, 'forum/post_detail.html', ctx)

    ctx = _post_detail_context(
        post, request,
        collection=collection,
        prev_post=prev_cp.post if prev_cp else None,
        next_post=next_cp.post if next_cp else None,
        all_cps=all_cps,
    )
    return render(request, 'forum/post_detail.html', ctx)


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
            messages.success(request, f'帖子已添加到合集「{collection.name}」。')
        else:
            messages.info(request, '帖子已在该合集中，无需重复添加。')
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
        logger.warning(
            "UserRegistrationView API 校验失败: errors=%s", serializer.errors,
        )
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
    """编辑自己的资料：头像、简介、个人网站、所在地。"""
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, '资料已更新。')
            return redirect('profile', username=request.user.username)
        messages.error(request, '资料保存失败，请检查下面的提示。')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'forum/profile_edit.html', {'form': form, 'profile': profile})
