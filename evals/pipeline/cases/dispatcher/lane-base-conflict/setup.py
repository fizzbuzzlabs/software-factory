def setup(context):
    """The ticket branch and main both rewrote the same line since the branch was cut."""
    ticket = context.tickets["ACM-50"]
    context.commit_on(ticket["branch"], {"src/app.txt": "sample-app, renamed by the ticket\n"},
                      "ACM-50: banner draft")
    context.write({"src/app.txt": "sample-app, renamed on main\n"})
    context.git("add", "-A")
    context.git("commit", "-m", "Rename the banner on main")
    context.git("push", "origin", "main")
