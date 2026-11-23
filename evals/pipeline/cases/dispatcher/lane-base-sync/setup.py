def setup(context):
    """Main moved on, without conflict, after the ticket branch was cut."""
    context.write({"src/unrelated.txt": "landed on main after the ticket branched\n"})
    context.git("add", "-A")
    context.git("commit", "-m", "Unrelated change on main")
    context.git("push", "origin", "main")
    ticket = context.tickets["ACM-55"]
    with open(context.state + "/branch-tip-before.txt", "w") as handle:
        handle.write(context.git("rev-parse", "refs/heads/" + ticket["branch"]))
