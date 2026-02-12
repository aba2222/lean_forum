class BotBase():
    def __init__(self, manager, name, id):
        self.manager = manager
        self.name = name
        self.id = id

    def handler(self, post, content):
        self.manager.send_comment(post, self.id, "Hello! I'm bot base.")
