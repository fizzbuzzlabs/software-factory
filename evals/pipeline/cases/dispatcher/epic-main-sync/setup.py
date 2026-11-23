def setup(context):
    """Both slices are merged into the epic branch, and main has moved on since: no slice launches this run."""
    epic = context.tickets["ACM-290"]["branch"]
    context.git("switch", epic)
    for key in ("ACM-291", "ACM-292"):
        context.git("merge", "--no-ff", "-m", "Merge slice %s into epic ACM-290" % key, context.tickets[key]["branch"])
    context.git("push", "origin", epic)
    context.git("switch", "main")
    context.write({"src/footer.txt": "footer added on main\n"})
    context.git("add", "-A")
    context.git("commit", "-m", "Add a footer on main")
    context.git("push", "origin", "main")
