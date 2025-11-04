from rich.console import Console
from astrid.context import Context

console = Console()

with console.status("Loading LLM Processor Dependencies..."):
    # from litellm import completion
    import os
    import time
    import random


class LLMProcessor:

    def __init__(self, ctx: Context):
        self.ctx = ctx

    def process_mock(self, input_text: str, model: str) -> str:
        # sleep for a random time to simulate processing
        time.sleep(random.uniform(0, 1))
        return f"Response to {input_text}"

    def process_real(self, input_text: str, model: str) -> str:
        ## set ENV variables
        os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

        with console.status("Thinking..."):
            response = completion(
                model="openai/gpt-5-nano",
                messages=[{"content": "Hello, how are you?", "role": "user"}],
            )

        return response.choices[0].message["content"]
