# python-relations-unifist

Relations Models for local generation ready for global adressing

Part of [Relations](https://github.com/relations-dil/python-relations). Source agnostic: it builds on the
core library's `Source`, `Model` and hooks only, so it works over any relations source.

## The Unifist source

The tables for ids, slugs and the journal live in a regular source named `unifist`. To use another name,
change it once on the lib, then make a source with that name when your app starts, separate from the source
your own models are in:

```python
import relations_pymysql
import relations_unifist

relations_unifist.UnifistBase.SOURCE = "ledger-unifist"   # the default is "unifist"

relations_pymysql.Source(relations_unifist.UnifistBase.SOURCE, schema="ledger_unifist", autocommit=True, host="mysql")
```

## Serving models

`relations_restx.attach` serves every model at the root, `/{singular}`. To serve them under `/model` instead, with
`/action` and `/view` lists beside them, attach with `relations_unifist.attach`:

```python
import flask
import relations_restx
import relations_unifist

app = flask.Flask("api")
restx = relations_restx.Api(app)

relations_unifist.attach(restx, resources_module, models)
```

- `GET /model` lists the models, `{"models": [...]}`, as `relations_restx.attach` does.
- Each model is at `/model/{singular}` and, if it has an id, `/model/{singular}/<id>`, with the same methods
  (`OPTIONS`, `GET`, `POST`, `PATCH`, `DELETE`) as in relations_restx. The OpenAPI spec lists these paths.
- `GET /action` is `{"actions": []}` and `GET /view` is `{"views": []}`, empty until something is registered.
  Pass lists as `actions=` and `views=` to `attach` to serve them. They are placeholders for now.

To write the resource for a model yourself, subclass `relations_unifist.Resource` the way you would
`relations_restx.Resource`:

```python
class PersonResource(relations_unifist.Resource):
    MODEL = Person
```

**Status:** scaffold. See the first ticket for the design and what done looks like.
