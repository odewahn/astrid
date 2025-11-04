from astrid.config import settings


class Context:
    def __init__(self, system_prompt: str = settings.system_prompt):
        self.context = [{"content": system_prompt, "role": "system"}]

    def append(self, content, role):
        self.context.append({"content": content, "role": role})

    def get_context(self):
        return self.context
