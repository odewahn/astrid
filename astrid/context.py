class Context:
    def __init__(self):
        self.context = []

    def append(self, content, role):
        self.context.append({"content": content, "role": role})

    def get_context(self):
        return self.context
