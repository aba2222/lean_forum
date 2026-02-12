from forum.bots.bot import BotBase

class ChatBot(BotBase):
    def __init__(self, manager, name, id):
        super().__init__(manager, name, id)

    def handler(self, post, context):
        super().handler(post, context)
        print("a")
