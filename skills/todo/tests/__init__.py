# Present so `python3 -m unittest discover -s tests -t .` collects anything at all.
#
# Not decoration: a refresh once deleted the equivalent file from a vendored skill, and the gated
# suite went on reporting OK while collecting zero tests — a green run that examined nothing
# (`.claude/rules/skills/lifecycle.md` § A Refresh Is Verified by Invocability). The matrix asserts
# a NON-ZERO collected count for the same reason.
