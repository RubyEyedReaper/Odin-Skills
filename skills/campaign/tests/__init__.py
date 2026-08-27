"""Marks the suite as a package.

MANDATORY. Without this file `unittest discover` collects zero tests from the skill
directory, the run exits 0, and the suite reports success having examined nothing — a
green from an instrument that never looked. `ci-local.sh` treats a zero-collected run as
a failure for exactly this reason.
"""
