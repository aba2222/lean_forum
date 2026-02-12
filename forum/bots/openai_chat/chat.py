from forum.bots.bot import BotBase

import os
from openai import OpenAI

class ChatBot(BotBase):
    def __init__(self, manager, name, id):
        super().__init__(manager, name, id)
        self.client =  OpenAI(
            # configure it
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    def handler(self, context):
        prompt = f"""
Post Information(Please give a single concise reply):
Title: {context.get("title", "")}
Author: {context.get("author", "")}
Created At: {context.get("create_at", "")}

Content:
{context.get("content", "")}

Instructions:
- Reply in a friendly, engaging, and lighthearted way.
- Chat about life, fun, or general topics.
- Keep your reply concise.
""".strip()

        try:
            completion = self.client.chat.completions.create(
                # 模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
                model="qwen-plus",
                messages=[
                    {"role": "system", "content": "You are the AI (bot) of Lean Forum. Lean only means simple and colorful. Chat about life and fun. Be concise and friendly."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens="3000"
            )
            reply = completion.choices[0].message.content
        except Exception as e:
            reply = "Something wrong with the bot."
        self.manager.send_comment(context.get("id"), self.id, reply)
