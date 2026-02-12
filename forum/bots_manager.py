from django.contrib.auth.models import User
from django.db import transaction

from .models import Comment
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
        
        thread = threading.Thread(target=bot.handler, args=(post, post.content))
        thread.daemon = True
        thread.start()
    
    def register_bot(self, bot):
        self.bots[bot.name] = bot
    
    @staticmethod
    def send_comment(post, id, message):
        with transaction.atomic():
            Comment.objects.create(
                post = post,
                author = User.objects.get(id=id),
                content = message
            )

manager = BotsManager()
manager.register_bot(ChatBot(manager=manager, name="bot", id=1))
