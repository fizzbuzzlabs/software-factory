def setup(context):
    """Both slices are merged into the epic branch: the epic is ready to finish, and another run holds it."""
    epic = context.tickets["ACM-230"]["branch"]
    context.git("switch", epic)
    for key in ("ACM-231", "ACM-232"):
        context.git("merge", "--no-ff", "-m", "Merge %s into the epic" % key, context.tickets[key]["branch"])
    context.git("push", "origin", epic)
    context.git("switch", "main")
