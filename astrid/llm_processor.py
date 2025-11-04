from rich.console import Console
from astrid.context import Context


import os


class LLMProcessor:

    def __init__(self, console: Console, model: str = "mock"):
        self.console = console

    def stream(self, ctx: Context, model: str = "mock"):
        """Yield response tokens for the input text as they are generated."""
        if model == "mock":
            import time, random

            # get the last piece of user input
            input_text = ""
            for message in reversed(ctx.get_context()):
                if message["role"] == "user":
                    input_text = message["content"]
                    break
            response = f"Here is my response to {input_text}"
            for char in response:
                time.sleep(random.uniform(0, 0.05))
                yield char
            return

        with self.console.status("Loading LLM Processor Dependencies..."):
            from litellm import completion

        os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

        response_stream = completion(
            model=model,
            messages=ctx.get_context(),
            max_tokens=1024,
            stream=True,
        )
        for partial in response_stream:
            choice = partial.choices[0]
            if hasattr(choice, "delta"):
                content = choice.delta.get("content", "")
            else:
                content = choice.message.get("content", "")
            if content:
                yield content
