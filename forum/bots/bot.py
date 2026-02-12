class BotBase():
    def __init__(self, manager, name, id):
        self.manager = manager
        self.name = name
        self.id = id

    def handler(self, context):
        self.manager.send_comment(context.get(id), self.id, "Hello! I'm bot base.")
