# Changelog

All notable changes to python-relations-unifist are recorded here, newest first. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

## [0.0.1] - 2026-10-14

### Added
- The package scaffold: `relations_unifist` with the tooling every relations repo has (`Makefile` with `make help`, `scripts/` for releases, `Jenkinsfile`, `VERSION`, the changelog). Nothing is released from it yet.
- `relations_unifist.slugify(titles, length=32)` makes a dns style slug (lower case letters, digits and single dashes) from a name or a list of titles. It folds accents, drops what can't fold, cuts at the last dash within `length` (1 to 255) or at `length`, and raises a `ValueError` if nothing is left.
- `relations_unifist.microseconds()`, now as an int of microseconds since the Unix epoch, how every time is stored.
- The models `Sequence` (a counter per unum, source and model), `Slug` (a taken slug per unum, source and model) and `Journal` (every change, with `when` in microseconds and `what` as a dict).
