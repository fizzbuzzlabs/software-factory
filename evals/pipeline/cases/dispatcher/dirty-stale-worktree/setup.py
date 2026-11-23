import os


def setup(context):
    """A crashed worker left a worktree on the ticket branch, holding work it never committed."""
    ticket = context.tickets["ACM-40"]
    tree = os.path.join(context.repo, ".claude", "worktrees", "agent-a1b2c3d4")
    context.git("worktree", "add", tree, ticket["branch"])
    contract = os.path.join(tree, "workflows", ticket["folder"], "contract.md")
    with open(contract, "a") as handle:
        handle.write("\n- [ ] 3. Reject a reminder dated in the past.\n")
    context.write({"src/acm-40-date-guard.txt": "half-written guard\n"}, cwd=tree)
