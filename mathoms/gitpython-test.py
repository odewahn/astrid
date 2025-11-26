import git

repo = git.Repo.clone_from(
    "https://github.com/odewahn/astrid-hello-world.git",
    ".astrid-content",
    branch="main",
)
