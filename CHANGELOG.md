# Changelog

All notable changes to python-relations-unifist are recorded here, newest first. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [0.3.0] - 2026-10-22

### Changed
- `make release-check` and `make release` don't run `build`, `test`, `lint` and `setup` again: the Jenkins stages have just run them before the release stage, so it was the same work twice. Run them yourself before checking by hand, as `make release-check` is only the checks and `dist-check` now (relations-dil/python-relations#90).

## [0.2.0] - 2026-10-20

### Added
- `relations_unifist.Resource`, a `relations_restx.Resource` that serves its model under `/model`: `/model/{singular}` and, for a model with an id, `/model/{singular}/<id>`. `thy().endpoints()` lists those, so the OpenAPI generator, which goes through the URLs a resource lists, documents the new paths with no change of its own (relations-dil/python-relations-unifist#4).
- `relations_unifist.attach(restx, module, models, actions=None, views=None)`, the way to serve an app's models from here instead of `relations_restx.attach`. It reuses `relations_restx.resources()` and `ensure()` and serves `GET /model` as `relations_restx.attach` does, listing the models, but serves every model's resource under `/model/{singular}`, including the resources `ensure` makes and ones that subclass `relations_restx.Resource`. It adds `GET /action`, `{"actions": [...]}`, and `GET /view`, `{"views": [...]}`, both empty lists unless `actions` or `views` are given. These are placeholders, nothing registers actions or views yet.

### Changed
- Needs relations-restx 0.6.7, with the packages it pins (flask, Werkzeug, flask-restx, jsonschema, MarkupSafe and click) in `requirements.txt`.
- The `Dockerfile` and `make setup` use `python:3.13` rather than `python:3`, as flask 2.1.2 does not run on Python 3.14 and later.

## [0.1.0] - 2026-10-14

### Added
- The package scaffold: `relations_unifist` with the tooling every relations repo has (`Makefile` with `make help`, `scripts/` for releases, `Jenkinsfile`, `VERSION`, the changelog). Jenkins releases on a merge to `main`: a `release` stage (only on `main`) runs `make release`, which does nothing for a version that is already released and otherwise does the test release, the release and the tag (relations-dil/python-relations#80).
- `relations_unifist.slugify(titles, length=32)` makes a dns style slug (lower case letters, digits and single dashes) from a name or a list of titles. It folds accents, drops what can't fold, cuts at the last dash within `length` (1 to 255) or at `length`, and raises a `ValueError` if nothing is left.
- `relations_unifist.microseconds()`, an int of microseconds since the Unix epoch, how every time is stored.
- The tables `Sequence` (a counter per unum, source and model), `Slug` (a taken slug per unum, source and model) and `Journal` (every change), all on `UnifistBase`, whose `SOURCE` names the Unifist source, `unifist` unless changed once on the lib. The README shows how to change it and make the source.
- `UnifistModel`, the base of models whose ids are made for them. A model has an `id` string and a `version` int, checked when it is made (and a `SLUG` that names real fields), and `UNIFIST` (the Unifist source's name, for the app to make its source from), `UNUM` (the unum), `SLUG` and `JOURNAL` are set on the app's own base model like `SOURCE` is.
- Ids are global, `identifier:model.source:unum`. Without a `SLUG` the identifier is the next number from the `Sequence`, taken by updating the counter only where it still holds what was read, so nothing is given out twice. With a `SLUG` it is a slug of that field or list of fields, with `-1`, `-2` and so on added until the `Slug` table takes it. Either race that is lost is tried again.
- Hooks: a new record gets its id, the `version` goes up by one on an update that changed something, and a `Journal` row is written for every create, update and delete with `what` as `{action, app, block, id, before, after}`, the whole record before and after. `JOURNAL = False` turns the journal off for a process, say a daemon.
- The journal's id is the transaction, `version:identifier:resource:owner:writer`, the same in every unum it is written to. The owner is the unum in the record's id and the writer is this unum, unless `create`, `update` or `delete` is given `writer=` to write on behalf of another. A delete is the version after the one it removes.
- Writes are serialized: a bulk create, and an update or delete by a query, are done one record at a time, each with its own id, version and journal row, and return how many were written. They are not atomic yet.

Needs relations-dil 0.6.20 (relations-dil/python-relations#78, relations-dil/python-relations#80).
