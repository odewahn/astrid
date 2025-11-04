from rich.console import Console
from astrid.context import Context


import os


class LLMProcessor:

    def __init__(self, ctx: Context, console: Console, model: str = "mock"):
        self.ctx = ctx
        self.console = console

    def process(self, input_text: str, model: str = "mock") -> str:
        # Handle the mock model separately
        if model == "mock":
            # sleep for a random time to simulate processing
            import time
            import random

            time.sleep(random.uniform(0, 1))
            return f"Response to {input_text}"

        # Real processing goes here
        with self.console.status("Loading LLM Processor Dependencies..."):
            from litellm import completion

        ## set ENV variables
        os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

        response = completion(
            model=model,
            messages=[{"content": input_text, "role": "user"}],
        )

        return response.choices[0].message["content"]
