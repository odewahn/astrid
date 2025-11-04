from rich.console import Console
from astrid.context import Context


import os


class LLMProcessor:

    def __init__(self, ctx: Context, console: Console):
        self.ctx = ctx
        self.console = console

    def process_mock(self, input_text: str, model: str) -> str:
        # sleep for a random time to simulate processing
        import time
        import random

        time.sleep(random.uniform(0, 1))
        return f"Response to {input_text}"

    def process_real(self, input_text: str, model: str) -> str:
        with self.console.status("Loading LLM Processor Dependencies..."):
            from litellm import completion
        ## set ENV variables
        os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

        response = completion(
            model="openai/gpt-5-nano",
            messages=[{"content": "Hello, how are you?", "role": "user"}],
        )

        return response.choices[0].message["content"]
