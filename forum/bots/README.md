# AI Robot in Forum

This documentation describes how to use and create AI bots that can reply to posts in the forum.

---

## How to use the AI bot

There is a pre-built AI bot implemented using OpenAI chat. To enable it, add the following line in `forum/bots_manager.py` and set an environment variable of key and model choice for your AI:

```python
manager.register_bot(ChatBot(manager=manager, name="bot", id=1))
```

---

## How to create your own bot

1. Create a folder structure like this:

```bash
forum/bots
├── bot.py
├── my_bot
│   ├── my_bot.py
└── README.md
```

2. Implement a class in `my_bot.py`, e.g., `MyBot`, that inherits from `BotBase` (defined in `bot.py`).

   * The `handler` function will be called whenever someone mentions `@bot_name`.
   * You can use `self.manager.send_comment(post_id, id, message)` to post a reply.

3. Register your bot in `forum/bots_manager.py`:

```python
manager.register_bot(MyBot(manager=manager, name="my_bot", id=2))
```

---

## APIs

### BotsManager

#### `register_bot(self, bot)`

Registers a bot with the bot manager.

**Example:**

```python
from forum.bots.openai_chat.chat import ChatBot

manager.register_bot(ChatBot(manager=manager, name="bot", id=1))
```

#### `send_comment(post_id, id, message)`

Sends a comment to the post with the given `post_id`.

* `id`: the user ID of the bot posting the comment
* `message`: the comment content

**Example:**

```python
self.manager.send_comment(1, 1, "Hello! This is a reply.")  # Make sure the id is valid
```

---

### BotBase

#### `__init__(self, manager, name, id)`

Initializes a bot.

* `manager`: the BotsManager instance
* `name`: the bot's display name
* `id`: the user ID representing the bot

#### `handler(self, context)`

This method is triggered when the bot is mentioned (`@bot_name`).
The `context` parameter is a dictionary containing:

```python
{
    "id": <post_id>,
    "title": <post_title>,
    "author": <author_name>,
    "content": <post_content>,
    "created_at": <timestamp>
}
```

Use this function to implement the bot’s behavior and reply using `self.manager.send_comment`.
