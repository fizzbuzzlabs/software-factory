def setup(context):
    """ACM-250's branch adds src/shared.txt; ACM-251's dev will add the same file with other content."""
    context.commit_on(context.tickets["ACM-250"]["branch"], {"src/shared.txt": "header written by ACM-250\n"},
                      "ACM-250: shared header")
