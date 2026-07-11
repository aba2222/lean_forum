from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User


from .models import Post, Comment, Item, Rating

# Create your tests here.

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
