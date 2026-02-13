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
        other = User.objects.create_user('other', password='p2')
        Rating.objects.create(user=self.user, item=self.item, score=3)
        Rating.objects.create(user=other, item=self.item, score=5)
        self.assertAlmostEqual(self.item.average_rating(), 4.0)

    def test_anonymous_cannot_create_post(self):
        url = reverse('post_create')
        resp = self.client.post(url, {'title': 'NoAuth', 'content': 'Should not work'})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Post.objects.filter(title='NoAuth').exists())

    def test_post_delete_only_author(self):
        other = User.objects.create_user('other2', password='p3')
        post = Post.objects.create(author=self.user, title='to_delete', content='c')
        # login as different user
        self.client.login(username='other2', password='p3')
        url = reverse('post_delete', kwargs={'pk': post.id})
        resp = self.client.post(url)
        # Other user should not be allowed to delete (404 from queryset filter)
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Post.objects.filter(id=post.id).exists())

    def test_item_str_and_average_zero(self):
        # Newly created item without ratings should report 0 average
        self.assertAlmostEqual(self.item.average_rating(), 0)
        self.assertIn('(avg: 0.0)', str(self.item))

    def test_register_view_creates_user(self):
        url = reverse('register')
        resp = self.client.post(url, {'username': 'newuser', 'password': 'pw1', 'confirm_password': 'pw1'}, follow=True)
        self.assertEqual(User.objects.filter(username='newuser').count(), 1)
        new_user = User.objects.get(username='newuser')
        self.assertTrue(new_user.check_password('pw1'))
