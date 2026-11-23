def setup(context):
    """The epic branch and main both rewrote the same line since the epic branch was cut."""
    epic = context.tickets["ACM-290"]["branch"]
    context.git("switch", epic)
    for key in ("ACM-291", "ACM-292"):
        context.git("merge", "--no-ff", "-m", "Merge slice %s into epic ACM-290" % key, context.tickets[key]["branch"])
    context.write({"src/app.txt": "sample-app, renamed by the epic\n"})
    context.git("add", "-A")
    context.git("commit", "-m", "ACM-290: rename the banner")
    context.git("push", "origin", epic)
    context.git("switch", "main")
    context.write({"src/app.txt": "sample-app, renamed on main\n"})
    context.git("add", "-A")
    context.git("commit", "-m", "Rename the banner on main")
    context.git("push", "origin", "main")
