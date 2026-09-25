from django.contrib.auth.models import User
from django.db import transaction

from .models import Comment, Post
from forum.bots.openai_chat.chat import ChatBot
import threading

class BotsManager():
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.bots = {}
        return cls._instance
    
    def at_bot(self, name, post):
        bot = self.bots.get(name)
        if bot is None:
            return
        
        context = {"id" : post.id, 
                   "title" : post.title,
                   "author" : post.author, 
                   "content" : post.content, 
                   "created_at" : post.created_at,
                    }
        thread = threading.Thread(target=bot.handler, args=(context,))
        thread.daemon = True
        thread.start()
    
    def register_bot(self, bot):
        self.bots[bot.name] = bot
    
    @staticmethod
    def send_comment(post_id, id, message):
        with transaction.atomic():
            try:
                post = Post.objects.get(id=post_id)
                author = User.objects.get(id=id)
            except (Post.DoesNotExist, User.DoesNotExist):
                # 帖子已被删除或机器人账号不存在，静默跳过
                return
            # 同一个机器人对同一个帖子只回一次同样的内容。
            # 被 @ 两次、handler 超时重试、线程重复启动都会走到这里，
            # 原来每次都是一个裸 create，于是出现两条一模一样的回复。
            if Comment.objects.filter(post=post, author=author, content=message).exists():
                return
            Comment.objects.create(
                post=post,
                author=author,
                content=message
            )

manager = BotsManager()
# manager.register_bot(ChatBot(manager=manager, name="bot", id=1))
