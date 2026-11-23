import os


def setup(context):
    """A crashed worker left a worktree on the ticket branch, with nothing uncommitted in it."""
    ticket = context.tickets["ACM-45"]
    tree = os.path.join(context.repo, ".claude", "worktrees", "agent-e5f6a7b8")
    context.git("worktree", "add", tree, ticket["branch"])
