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

    def handler(self, post, content):
        completion = self.client.chat.completions.create(
            # 模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
            model="qwen-plus",
            messages=[
                {"role": "system", "content": "You are bot, a helpful assistant for Lean Forum (https://lforum.dpdns.org/). Help users with questions and discussions. This forum is unrelated to the Lean theorem prover."},
                {"role": "user", "content": content},
            ]
        )
        reply = completion.choices[0].message.content
        self.manager.send_comment(post, self.id, reply)
