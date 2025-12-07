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
        self.item = Item.objects.create(name='Item1', description='desc')
    
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
