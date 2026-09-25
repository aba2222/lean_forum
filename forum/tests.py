from django.conf import settings
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template

import io
import os
import shutil
import tempfile

from PIL import Image

from . import search
from .avatars import AVATAR_MAX_BYTES, AVATAR_MAX_EDGE, avatar_url, fallback_color, fallback_initial
from .models import Post, Comment, Item, Rating, Profile

# Create your tests here.


def image_bytes(size=(1200, 800), fmt='PNG', mode='RGB', color=(180, 40, 60)):
    """生成一张真实可解码的图片，用于测试头像上传。"""
    buffer = io.BytesIO()
    Image.new(mode, size, color).save(buffer, fmt)
    return buffer.getvalue()


def upload_image(name='avatar.png', **kwargs):
    fmt = kwargs.pop('fmt', 'PNG')
    return SimpleUploadedFile(name, image_bytes(fmt=fmt, **kwargs), content_type='image/png')


def oversize_png():
    """构造一个体积超限、但仍能被 Pillow 正常解码的 PNG（IEND 之后补零）。"""
    raw = image_bytes(size=(64, 64))
    return raw + b'\0' * (AVATAR_MAX_BYTES + 1 - len(raw))


def animated_image_bytes(fmt='GIF', frames=3, size=(800, 800), duration=137):
    """生成一张真实的多帧图，左上角 1/4 是透明区域。

    透明度要真的写进去（paste 一整块 alpha=0），否则「保留透明」的断言
    在量化之后无论如何都会通过，测不出东西。
    """
    images = []
    for index in range(frames):
        # 每帧都要真的不一样：Pillow 的 GIF 编码器会跳过与上一帧内容相同的帧，
        # 用重复帧造测试图会得到比预期少得多的 n_frames，测不出帧数上限。
        shade = 30 + (index * 37) % 200
        frame = Image.new('RGBA', size, (shade, 90, 200, 255))
        frame.paste((0, 0, 0, 0), (0, 0, size[0] // 2, size[1] // 2))
        offset = index % max(1, size[0] // 4)
        frame.paste((250, 240, 20, 255), (offset, 0, offset + 6, 6))
        images.append(frame)

    buffer = io.BytesIO()
    images[0].save(
        buffer,
        fmt,
        save_all=True,
        append_images=images[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )
    return buffer.getvalue()


def upload_animated(name='avatar.gif', fmt='GIF', **kwargs):
    content_type = 'image/gif' if fmt == 'GIF' else 'image/webp'
    return SimpleUploadedFile(
        name, animated_image_bytes(fmt=fmt, **kwargs), content_type=content_type
    )


def corner_alpha(image, steps=17):
    """取左上角 1/4 区域的平均 alpha——多帧图用来判断透明有没有被压掉。"""
    rgba = image.convert('RGBA')
    width, height = rgba.size
    samples = [
        rgba.getpixel((x, y))[3]
        for x in range(0, max(1, width // 4), steps)
        for y in range(0, max(1, height // 4), steps)
    ]
    return sum(samples) / len(samples)


class ForumTests(TestCase):
    def setUp(self):
        self.username = 'testuser'
        self.password = 'pass12345'
        self.user = User.objects.create_user(self.username, password=self.password)
        self.user2 = User.objects.create_user('other', password='p2')
        self.item = Item.objects.create(name='Item1', content='desc')
    
    def test_create_post(self):
        self.client.login(username=self.username, password=self.password)
        url = reverse('post_create')
        data = {'title': 'Hello', 'content': 'This is content'}
        resp = self.client.post(url, data)

        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Post.objects.filter(title='Hello', author=self.user).exists())

    def test_comment_create(self):
        post = Post.objects.create(author=self.user, title='t', content='c')
        url = reverse('post_detail', kwargs={'post_id': post.id})

        # Not logged in
        resp = self.client.post(url, {'content': 'nice'})
        self.assertEqual(Comment.objects.count(), 0)

        # Logged in
        self.client.login(username=self.username, password=self.password)
        resp = self.client.post(url, {'content': 'nice'}, follow=True)
        self.assertEqual(Comment.objects.count(), 1)
        c = Comment.objects.first()
        self.assertEqual(c.post, post)
        self.assertEqual(c.author, self.user)
        self.assertEqual(c.content, 'nice')

    def test_rate_item_and_unique_constraint(self):
        url = reverse('rate_item', kwargs={'item_id': self.item.id})

        # Not logged in
        resp = self.client.post(url, {'score': '3'})
        self.assertEqual(Rating.objects.count(), 0)

        # Logged in
        self.client.login(username=self.username, password=self.password)
        resp = self.client.post(url, {'score': '4'}, follow=True)
        self.assertEqual(Rating.objects.count(), 1)
        r = Rating.objects.get(user=self.user, item=self.item)
        self.assertEqual(r.score, 4)

        # Commit update
        resp = self.client.post(url, {'score': '2'}, follow=True)
        self.assertEqual(Rating.objects.count(), 1)
        r.refresh_from_db()
        self.assertEqual(r.score, 2)
    
    def test_average_rating_method(self):
        Rating.objects.create(user=self.user, item=self.item, score=3)
        Rating.objects.create(user=self.user2, item=self.item, score=5)
        self.assertAlmostEqual(self.item.average_rating(), 4.0)

    def test_anonymous_cannot_create_post(self):
        url = reverse('post_create')
        resp = self.client.post(url, {'title': 'NoAuth', 'content': 'Should not work'})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Post.objects.filter(title='NoAuth').exists())

    def test_api_create_post_and_comment(self):
        posts_url = reverse('post-list')

        # Unauthorized
        anon_resp = self.client.post(
            posts_url,
            {'title': 'API Post', 'content': 'hello from api'},
            content_type='application/json',
        )
        self.assertEqual(anon_resp.status_code, 401)

        # Get JWT token for the user
        token_resp = self.client.post(
            reverse('token_obtain_pair'),
            {'username': self.username, 'password': self.password},
            content_type='application/json',
        )
        self.assertEqual(token_resp.status_code, 200)
        access_token = token_resp.json()['access']
        create_resp = self.client.post(
            posts_url,
            {'title': 'API Post', 'content': 'hello from api'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {access_token}',
        )
        self.assertEqual(create_resp.status_code, 201)
        self.assertTrue(Post.objects.filter(title='API Post', author=self.user).exists())

        post = Post.objects.get(title='API Post', author=self.user)
        comments_url = reverse('post-comments', kwargs={'pk': post.id})
        comment_resp = self.client.post(
            comments_url,
            {'content': 'nice api comment'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {access_token}',
        )
        self.assertEqual(comment_resp.status_code, 201)
        self.assertTrue(Comment.objects.filter(post=post, author=self.user, content='nice api comment').exists())

    def test_nav_search_form_uses_search_query(self):
        response = self.client.get(reverse('index'))

        self.assertContains(response, 'name="q"')
        self.assertContains(response, f'action="{reverse("post_list")}"')
        self.assertContains(response, 'method="get"')

    def test_api_others_cannot_delete_post(self):
        post = Post.objects.create(author=self.user, title='to_delete', content='c')
        url = reverse('post-detail', kwargs={'pk': post.id})

        # anonymous user should not be able to delete
        resp = self.client.delete(url)

        self.assertEqual(resp.status_code, 401)
        self.assertTrue(Post.objects.filter(id=post.id).exists())

        # logged in as different user
        self.client.login(username='other', password='p2')
        resp = self.client.delete(url)

        self.assertEqual(resp.status_code, 401)
        self.assertTrue(Post.objects.filter(id=post.id).exists())

    def test_upload_view_saves_image_to_storage(self):
        self.client.login(username=self.username, password=self.password)
        image = SimpleUploadedFile(
            'test-image.jpg',
            b'fake-image-bytes',
            content_type='image/jpeg',
        )

        response = self.client.post(reverse('upload_view'), {'image': image})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['url'].startswith(settings.MEDIA_URL))

        relative_path = payload['url'].removeprefix(settings.MEDIA_URL)
        self.assertFalse(relative_path.startswith('/'))
        self.assertTrue(relative_path.endswith('.jpg'))

    def test_post_delete_only_author(self):
        post = Post.objects.create(author=self.user, title='to_delete', content='c')
        # login as different user
        self.client.login(username='other', password='p2')
        url = reverse('post_delete', kwargs={'pk': post.id})
        resp = self.client.post(url)
        # Other user should not be allowed to delete (404 from queryset filter)
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Post.objects.filter(id=post.id).exists())

    def test_item_str_and_average_zero(self):
        # Newly created item without ratings should report 0 average
        self.assertAlmostEqual(self.item.average_rating(), 0)
        self.assertIn('(avg: 0.0)', str(self.item))
    
    def test_register_api_creates_user(self):
        url = reverse('register_api')
        resp = self.client.post(url, {'username': 'newuser', 'password': 'pw1', 'password2': 'pw1'}, content_type='application/json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(User.objects.filter(username='newuser').exists())
        new_user = User.objects.get(username='newuser')
        self.assertTrue(new_user.check_password('pw1'))

    def test_register_view_creates_user(self):
        url = reverse('register')
        resp = self.client.post(url, {'username': 'newuser2', 'password': 'pw1', 'confirm_password': 'pw1'}, follow=True)
        self.assertEqual(User.objects.filter(username='newuser2').count(), 1)
        new_user = User.objects.get(username='newuser2')
        self.assertTrue(new_user.check_password('pw1'))


class AvatarHelperTests(TestCase):
    """默认字母头像的配色/首字，以及头像压缩归一化。"""

    def test_fallback_color_is_stable_and_from_palette(self):
        self.assertEqual(fallback_color('xiokuai'), fallback_color('xiokuai'))
        self.assertNotEqual(fallback_color(''), '')

    def test_fallback_initial(self):
        self.assertEqual(fallback_initial('xiokuai'), 'X')
        self.assertEqual(fallback_initial('  测试用户'), '测')
        self.assertEqual(fallback_initial(''), '?')
        self.assertEqual(fallback_initial(None), '?')

    def test_normalize_shrinks_and_converts_to_jpeg(self):
        from .avatars import normalize_avatar

        normalized = normalize_avatar(upload_image(size=(1200, 800)))
        image = Image.open(normalized)
        self.assertEqual(image.format, 'JPEG')
        self.assertLessEqual(max(image.size), AVATAR_MAX_EDGE)

    def test_normalize_keeps_transparency_as_png(self):
        from .avatars import normalize_avatar

        normalized = normalize_avatar(
            upload_image(name='a.png', size=(600, 600), mode='RGBA', color=(0, 0, 0, 0))
        )
        self.assertEqual(Image.open(normalized).format, 'PNG')

    def test_normalize_rejects_non_image(self):
        from django.core.exceptions import ValidationError

        from .avatars import normalize_avatar

        with self.assertRaises(ValidationError):
            normalize_avatar(SimpleUploadedFile('x.png', b'not-an-image', content_type='image/png'))

    def test_normalize_rejects_oversize(self):
        from django.core.exceptions import ValidationError

        from .avatars import normalize_avatar

        payload = oversize_png()
        self.assertGreater(len(payload), AVATAR_MAX_BYTES)

        with self.assertRaises(ValidationError):
            normalize_avatar(SimpleUploadedFile('big.png', payload, content_type='image/png'))

    def test_normalize_keeps_gif_animation(self):
        from .avatars import normalize_avatar

        normalized = normalize_avatar(upload_animated(fmt='GIF', frames=4))

        self.assertEqual(normalized.name, 'avatar.gif')
        with Image.open(io.BytesIO(normalized.read())) as image:
            self.assertEqual(image.format, 'GIF')
            self.assertTrue(getattr(image, 'is_animated', False))
            self.assertEqual(image.n_frames, 4)
            self.assertLessEqual(max(image.size), AVATAR_MAX_EDGE)
            image.seek(0)
            # 每帧都要被缩放，而不是只缩放首帧
            self.assertLessEqual(max(image.size), AVATAR_MAX_EDGE)

    def test_normalize_keeps_webp_animation(self):
        from .avatars import normalize_avatar

        normalized = normalize_avatar(upload_animated(name='a.webp', fmt='WEBP', frames=3))

        self.assertEqual(normalized.name, 'avatar.webp')
        with Image.open(io.BytesIO(normalized.read())) as image:
            self.assertEqual(image.format, 'WEBP')
            self.assertTrue(getattr(image, 'is_animated', False))
            self.assertEqual(image.n_frames, 3)
            self.assertLessEqual(max(image.size), AVATAR_MAX_EDGE)

    def test_normalize_keeps_transparency_in_animation(self):
        """动图重编码后透明区域要还是透明的。

        这里踩过一次坑：直接把 RGBA 帧 convert('P') 会把透明像素当成
        不透明颜色一起量化掉，透明背景会变成一块实色。
        """
        from .avatars import normalize_avatar

        normalized = normalize_avatar(upload_animated(fmt='GIF', frames=2))

        with Image.open(io.BytesIO(normalized.read())) as image:
            image.seek(0)
            self.assertLess(corner_alpha(image), 16)

    def test_normalize_single_frame_gif_is_treated_as_static(self):
        """单帧 GIF 没有动画可保，应该退回静态分支存成 JPEG。"""
        from .avatars import normalize_avatar

        normalized = normalize_avatar(
            SimpleUploadedFile('one.gif', image_bytes(fmt='GIF'), content_type='image/gif')
        )

        self.assertEqual(normalized.name, 'avatar.jpg')

    def test_normalize_rejects_too_many_animated_frames(self):
        from django.core.exceptions import ValidationError

        from .avatars import ANIMATED_AVATAR_MAX_FRAMES, normalize_avatar

        upload = upload_animated(frames=ANIMATED_AVATAR_MAX_FRAMES + 1, size=(64, 64))

        with self.assertRaises(ValidationError) as ctx:
            normalize_avatar(upload)
        self.assertIn('帧', str(ctx.exception))

    def test_normalize_still_rejects_oversize_static_gif(self):
        """动图上限定得更松，但静态图仍然卡原来的 2 MB。"""
        from django.core.exceptions import ValidationError

        from .avatars import normalize_avatar

        payload = image_bytes(size=(64, 64), fmt='GIF') + b'\0' * (AVATAR_MAX_BYTES + 1)
        upload = SimpleUploadedFile('big.gif', payload, content_type='image/gif')

        with self.assertRaises(ValidationError):
            normalize_avatar(upload)


class ProfileTests(TestCase):
    """个人主页 + 头像功能。"""

    @classmethod
    def setUpClass(cls):
        cls._media_root = tempfile.mkdtemp(prefix='lean_forum_test_media_')
        cls._overrides = override_settings(
            # 头像测试写到临时目录，别污染仓库里的 uploads/
            MEDIA_ROOT=cls._media_root,
            # 测试里不需要真实密码强度，默认 PBKDF2 会让每个用户多花近一秒
            PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
        )
        cls._overrides.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._overrides.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user('xiokuai', password='pw12345')
        self.other = User.objects.create_user('friend', password='pw12345')
        self.client.login(username='xiokuai', password='pw12345')

    # ---- 模型与建档 ----

    def test_new_user_gets_profile_automatically(self):
        self.assertTrue(Profile.objects.filter(user=self.user).exists())
        self.assertFalse(bool(self.user.profile.avatar))

    def test_profile_view_creates_profile_when_missing(self):
        # 模拟历史用户：表里有用户但还没有 Profile
        Profile.objects.filter(user=self.other).delete()
        resp = self.client.get(reverse('profile', kwargs={'username': 'friend'}))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Profile.objects.filter(user=self.other).exists())

    # ---- 个人主页 ----

    def test_profile_page_only_shows_this_user_content(self):
        Post.objects.create(author=self.user, title='我的帖子', content='hi')
        Post.objects.create(author=self.other, title='别人的帖子', content='hi')

        resp = self.client.get(reverse('profile', kwargs={'username': 'xiokuai'}))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '我的帖子')
        self.assertNotContains(resp, '别人的帖子')
        self.assertEqual(resp.context['stats']['posts'], 1)
        self.assertTrue(resp.context['is_self'])

    def test_profile_page_visible_to_anonymous(self):
        self.client.logout()
        resp = self.client.get(reverse('profile', kwargs={'username': 'xiokuai'}))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['is_self'])

    def test_profile_page_unknown_user_returns_404(self):
        resp = self.client.get(reverse('profile', kwargs={'username': 'nobody'}))
        self.assertEqual(resp.status_code, 404)

    def test_profile_page_supports_chinese_username(self):
        User.objects.create_user('测试用户', password='pw12345')
        resp = self.client.get('/u/测试用户/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '测试用户')

    def test_profile_stats_count_posts_comments_collections_and_views(self):
        post = Post.objects.create(author=self.user, title='帖子', content='x', views=7)
        Post.objects.create(author=self.other, title='别人的', content='x', views=100)
        Comment.objects.create(post=post, author=self.user, content='自评')
        from .models import Collection

        Collection.objects.create(owner=self.user, name='我的合集', content='')

        resp = self.client.get(reverse('profile', kwargs={'username': 'xiokuai'}))

        self.assertEqual(resp.context['stats']['posts'], 1)
        self.assertEqual(resp.context['stats']['comments'], 1)
        self.assertEqual(resp.context['stats']['collections'], 1)
        self.assertEqual(resp.context['stats']['views'], 7)

    def test_profile_tabs_and_pagination(self):
        for index in range(12):
            Post.objects.create(author=self.user, title=f'第{index}篇', content='x')

        first = self.client.get(reverse('profile', kwargs={'username': 'xiokuai'}))
        self.assertEqual(first.context['tab'], 'posts')
        self.assertEqual(len(first.context['page_obj'].object_list), 10)

        second = self.client.get('/u/xiokuai/?tab=posts&page=2')
        self.assertEqual(len(second.context['page_obj'].object_list), 2)

        comments_tab = self.client.get('/u/xiokuai/?tab=comments')
        self.assertEqual(comments_tab.context['tab'], 'comments')

        # 非法 tab 回落到帖子
        fallback = self.client.get('/u/xiokuai/?tab=<script>')
        self.assertEqual(fallback.context['tab'], 'posts')

    # ---- 资料编辑 ----

    def test_profile_edit_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('profile_edit'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('login'), resp.url)

    def test_profile_edit_updates_fields_and_renders_markdown(self):
        resp = self.client.post(
            reverse('profile_edit'),
            {
                'content': '**你好**，我是 xiokuai',
                'website': 'https://example.com',
                'location': '杭州',
            },
        )

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('profile', kwargs={'username': 'xiokuai'}))

        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.location, '杭州')
        self.assertEqual(profile.website, 'https://example.com')
        self.assertIn('<strong>你好</strong>', profile.content_html)

        page = self.client.get(reverse('profile', kwargs={'username': 'xiokuai'}))
        self.assertContains(page, '<strong>你好</strong>', html=False)
        self.assertContains(page, '杭州')

    def test_profile_edit_rejects_too_long_bio(self):
        resp = self.client.post(reverse('profile_edit'), {'content': '字' * 2001})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('content', resp.context['form'].errors)

    def test_profile_edit_allows_bio_up_to_200_chars(self):
        long_bio = '字' * 200
        resp = self.client.post(
            reverse('profile_edit'),
            {'content': long_bio, 'website': '', 'location': ''},
        )

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Profile.objects.get(user=self.user).content, long_bio)

    def test_avatar_url_handles_user_without_profile(self):
        user_without_profile = User.objects.create_user('no_profile_user', password='pw12345')
        Profile.objects.filter(user=user_without_profile).delete()

        self.assertEqual(avatar_url(user_without_profile), '')

    def test_profile_edit_renders_markdown_editor(self):
        resp = self.client.get(reverse('profile_edit'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'md_editor')

    # ---- 头像 ----

    def test_avatar_upload_is_saved_and_resized(self):
        resp = self.client.post(
            reverse('profile_edit'),
            {'content': '', 'website': '', 'location': '', 'avatar': upload_image(size=(1600, 900))},
        )
        self.assertEqual(resp.status_code, 302)

        profile = Profile.objects.get(user=self.user)
        self.assertTrue(profile.avatar.name.startswith('avatars/u'))
        self.assertTrue(os.path.exists(profile.avatar.path))

        with Image.open(profile.avatar.path) as image:
            self.assertLessEqual(max(image.size), AVATAR_MAX_EDGE)

    def test_animated_gif_avatar_is_stored_as_gif(self):
        """端到端：上传动图后落盘的是 .gif，而且动画还在。"""
        resp = self.client.post(
            reverse('profile_edit'),
            {'content': '', 'website': '', 'location': '', 'avatar': upload_animated(frames=4)},
        )
        self.assertEqual(resp.status_code, 302)

        profile = Profile.objects.get(user=self.user)
        self.assertTrue(profile.avatar.name.endswith('.gif'), profile.avatar.name)
        self.assertTrue(profile.avatar.name.startswith('avatars/u'))

        with Image.open(profile.avatar.path) as image:
            self.assertTrue(getattr(image, 'is_animated', False))
            self.assertEqual(image.n_frames, 4)
            self.assertLessEqual(max(image.size), AVATAR_MAX_EDGE)

    def test_animated_avatar_renders_as_plain_img_tag(self):
        """动图在页面上就是一个普通 <img>，不需要额外的前端改动。"""
        self.client.post(
            reverse('profile_edit'),
            {'content': '', 'website': '', 'location': '', 'avatar': upload_animated(frames=3)},
        )
        profile = Profile.objects.get(user=self.user)
        self.user.refresh_from_db()  # profile 关系可能还是旧的缓存

        rendered = Template('{% load forum_extras %}{% avatar u 40 %}').render(
            Context({'u': self.user})
        )
        self.assertIn('avatar-img', rendered)
        self.assertIn(profile.avatar.url, rendered)

    def test_avatar_upload_rejects_non_image(self):
        resp = self.client.post(
            reverse('profile_edit'),
            {
                'content': '',
                'website': '',
                'location': '',
                'avatar': SimpleUploadedFile('evil.png', b'hello', content_type='image/png'),
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertIn('avatar', resp.context['form'].errors)
        self.assertFalse(bool(Profile.objects.get(user=self.user).avatar))

    def test_avatar_upload_rejects_oversize(self):
        resp = self.client.post(
            reverse('profile_edit'),
            {
                'content': '',
                'website': '',
                'location': '',
                'avatar': SimpleUploadedFile(
                    'big.png', oversize_png(), content_type='image/png'
                ),
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertIn('avatar', resp.context['form'].errors)
        self.assertFalse(bool(Profile.objects.get(user=self.user).avatar))

    def test_avatar_kept_when_form_submitted_without_new_file(self):
        self.client.post(
            reverse('profile_edit'),
            {'content': '', 'website': '', 'location': '', 'avatar': upload_image()},
        )
        before = Profile.objects.get(user=self.user).avatar.name

        self.client.post(reverse('profile_edit'), {'content': '只改简介', 'website': '', 'location': ''})

        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.avatar.name, before)
        self.assertTrue(os.path.exists(profile.avatar.path))
        self.assertEqual(profile.content, '只改简介')

    def test_avatar_replace_deletes_old_file(self):
        self.client.post(
            reverse('profile_edit'),
            {'content': '', 'website': '', 'location': '', 'avatar': upload_image()},
        )
        first_path = Profile.objects.get(user=self.user).avatar.path
        self.assertTrue(os.path.exists(first_path))

        self.client.post(
            reverse('profile_edit'),
            {
                'content': '',
                'website': '',
                'location': '',
                'avatar': upload_image(size=(400, 400), color=(10, 90, 200)),
            },
        )

        second_path = Profile.objects.get(user=self.user).avatar.path
        self.assertNotEqual(first_path, second_path)
        self.assertTrue(os.path.exists(second_path))
        self.assertFalse(os.path.exists(first_path))

    def test_avatar_clear_removes_avatar_and_file(self):
        self.client.post(
            reverse('profile_edit'),
            {'content': '', 'website': '', 'location': '', 'avatar': upload_image()},
        )
        path = Profile.objects.get(user=self.user).avatar.path
        self.assertTrue(os.path.exists(path))

        self.client.post(
            reverse('profile_edit'),
            {'content': '', 'website': '', 'location': '', 'avatar-clear': 'on'},
        )

        profile = Profile.objects.get(user=self.user)
        self.assertFalse(bool(profile.avatar))
        self.assertFalse(os.path.exists(path))

    # ---- 头像在页面上的呈现 ----

    def test_avatar_tag_falls_back_to_initial(self):
        rendered = Template('{% load forum_extras %}{% avatar u 40 %}').render(
            Context({'u': self.user})
        )
        self.assertIn('avatar-initial', rendered)
        self.assertIn('>X<', rendered)
        self.assertIn('width: 40px', rendered)

    def test_avatar_tag_renders_image_when_avatar_exists(self):
        self.client.post(
            reverse('profile_edit'),
            {'content': '', 'website': '', 'location': '', 'avatar': upload_image()},
        )
        self.user.refresh_from_db()

        rendered = Template('{% load forum_extras %}{% avatar u 32 %}').render(
            Context({'u': self.user})
        )

        self.assertIn('avatar-img', rendered)
        self.assertIn(settings.MEDIA_URL, rendered)
        self.assertNotIn('avatar-initial', rendered)

    def test_avatar_tag_without_user_renders_placeholder(self):
        rendered = Template('{% load forum_extras %}{% avatar u 32 %}').render(Context({'u': None}))
        self.assertIn('avatar-initial', rendered)
        self.assertIn('匿名用户', rendered)

    def test_navbar_and_post_pages_link_to_profile(self):
        post = Post.objects.create(author=self.user, title='带头像的帖子', content='正文')
        Comment.objects.create(post=post, author=self.other, content='评论')

        profile_url = reverse('profile', kwargs={'username': 'xiokuai'})

        home = self.client.get(reverse('index'))
        self.assertContains(home, profile_url)

        detail = self.client.get(reverse('post_detail', kwargs={'post_id': post.id}))
        self.assertContains(detail, profile_url)
        self.assertContains(
            detail, reverse('profile', kwargs={'username': 'friend'})
        )
        self.assertContains(detail, 'avatar-initial')


class SearchTests(TransactionTestCase):
    """站内搜索：FTS5 命中、短查询回退、索引与源表同步。

    用 TransactionTestCase 而不是 TestCase：FTS5 虚表的创建与 rebuild 必须在
    事务之外执行（见 forum/search.py 的说明），TestCase 会把每个用例包在事务里
    并在结束时回滚，正好踩中 SQLite 的那个坑。
    """

    def setUp(self):
        self.user = User.objects.create_user('searcher', password='pw12345')
        self.other = User.objects.create_user('another', password='pw12345')

    def make_post(self, title, content, author=None):
        return Post.objects.create(author=author or self.user, title=title, content=content)

    # ---- 命中 ----

    def test_long_chinese_query_hits(self):
        self.make_post('最短路算法总结', 'dijkstra 与 SPFA 的对比')
        self.make_post('无关的一篇', '别的内容')
        self.assertEqual(
            [p.title for p in search.search_posts('最短路')], ['最短路算法总结']
        )

    def test_short_chinese_query_falls_back_and_still_hits(self):
        # 两字词用不上 trigram 索引，回退 LIKE 也必须搜得到
        self.make_post('图论入门', '这是一篇题解')
        self.assertEqual([p.title for p in search.search_posts('题解')], ['图论入门'])

    def test_searches_content_not_only_title(self):
        self.make_post('标题不相关', '正文里提到 单调队列优化')
        self.assertEqual([p.title for p in search.search_posts('单调队列')], ['标题不相关'])

    def test_search_by_author_name(self):
        self.make_post('随便一篇', '随便', author=self.other)
        self.assertEqual(search.search_posts('another').count(), 1)

    def test_empty_query_returns_everything(self):
        self.make_post('甲', 'x')
        self.make_post('乙', 'y')
        self.assertEqual(search.search_posts('').count(), 2)

    # ---- 索引是否真的用上了 ----

    def test_long_query_really_uses_fts_index(self):
        self.make_post('最短路算法总结', 'x')
        ids = search._fts_ids('最短路')
        self.assertIsNotNone(ids, 'FTS5 索引不可用，说明退化成了 LIKE')
        self.assertEqual(len(ids), 1)

    # ---- 索引与源表同步 ----

    def test_index_follows_update_and_delete(self):
        post = self.make_post('旧标题aaa', '旧内容aaa')
        self.assertEqual(search.search_posts('旧标题').count(), 1)

        post.title = '新标题bbb'
        post.content = '新内容bbb'
        post.save()
        self.assertEqual(search.search_posts('新标题').count(), 1)
        self.assertEqual(search.search_posts('旧标题').count(), 0)

        post.delete()
        self.assertEqual(search.search_posts('新标题').count(), 0)

    # ---- 健壮性 ----

    def test_fts_operator_characters_are_treated_as_text(self):
        self.make_post('一篇普通文章', '内容')
        # 这些都是 FTS5 的查询操作符，不能被当成语法
        for q in ['"', '*', '(', ')', 'NEAR(', 'a OR b', '标题"', '"未闭合']:
            list(search.search_posts(q))

    # ---- 页面 ----

    def test_post_list_page_uses_search(self):
        self.make_post('最短路算法总结', 'x')
        self.make_post('无关的一篇', 'y')
        resp = self.client.get(reverse('post_list'), {'q': '最短路'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['page_obj'].object_list), 1)
