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

## Security

Holding a model's verbs to rules is in relations itself, `relations.security` (relations-dil 0.7.0), and works with `UnifistModel`s as with any model. Mix `Secure` in front of the model, give it a policy, and say who is acting:

```python
import relations.security
import relations_unifist

class Doc(relations.security.Secure, relations_unifist.UnifistModel):
    SOURCE = "app"
    id = str
    version = int, 1
    unum = str
    owner = str
    title = str
    locked = bool, False

relations.security.POLICY = relations.security.Policy({
    "doc": {
        "retrieve": relations.security.Rule(scope=lambda actor: {"owner": actor}),
        "create": relations.security.Rule(scope=lambda actor: {"owner": actor}),
        "update": relations.security.Rule(scope=lambda actor: {"owner": actor, "locked": False}, into=lambda actor: {"owner": actor}),
        "delete": relations.security.Rule(scope=lambda actor: {"owner": actor, "locked": False})
    }
})

with relations.security.acting("pat"):
    Doc.many().title      # only pat's
```

- **No actor, or no rule, is no** (`Denied`). `count` and `titles` use `retrieve`'s rule unless given their own.
- **What an actor can't read is a miss**, as if it weren't there. **What they can read but can't write is `Denied`**, so they're told.
- **Scopes** are filter kwargs, or a function of the actor that gives them. On the model's own fields they're checked in memory, before the source; on relations they're added to the source's query (and can't be checked for a record that doesn't exist yet, so give the rule a `check`).
- **Bulk** `update` and `delete` are narrowed to what the actor can read and write in the query they already make.
- **`into`** is what new values have to satisfy on `create` and `update` (the scope if not given). `{}` allows any, which is how a record is moved out of reach, after which it can't be read.
- **`force`** sets values on `create` and `update` whatever was sent. **`fields`** are the names that can be read (`retrieve`) or written (`create`, `update`). **`check`** is a function of the actor and the record's values.
- **`filter`, `sort` and `like` can only use fields the actor can read**, or they'd be a way to find out what they can't. `secure(**scope)` is `filter` for what security adds, merged so it can't be widened. Rules for models filtered through (a relation's `folder__name`) are the related model's, so give them `fields` that include their ids.
- **`system()`** is for the code's own work, which isn't checked, like a policy reading its own rules.
- **Override `Policy.rule(actor, model, verb)`** to get rules from somewhere else, such as a Unifist source.

### Policy as data

`relations_policy` keeps the rules in tables, so they can be changed without a deploy, and as `PolicyBase` is a Unifist model they get global ids, versions and the journal. `Actor` is who acts, `Troupe` a group of them, `Casting(actor, troupe, part)` puts an actor in a troupe in a part, and `Charter` says what a part may do with a verb on a model:

```python
import relations_policy

relations_policy.PolicyBase.SOURCE = "policy"   # the default, change it once, and make the source when the app starts
relations.security.POLICY = relations_policy.Policy()

pat = relations_policy.Actor(name="pat").create()
red = relations_policy.Troupe(name="red").create()
relations_policy.Casting(actor=pat.id, troupe=red.id, part="writer").create()

relations_policy.Charter(
    part="writer", model="doc", verb="retrieve", scope={"troupe__in": "$troupes"}
).create()

with relations.security.acting(pat.id):
    Doc.many().title      # the docs of the troupes pat is cast in
```

- **Blank is any.** A charter with no troupe, part, model or verb applies to any, and the most specific one that matches the actor, model and verb gives the rule: the model first, then the verb (the one asked for, then the one it inherits, then any), then the troupe and part. Charters that tie with different rules are a `Denied`, not a guess, so give an actor in two troupes one charter with `$troupes` rather than one for each.
- **`$actor` and `$troupes`** in `scope`, `becomes` and `pins` are the actor's id and the ids of the troupes they're cast in. `allow=False` is a rule, and a more specific charter can allow what a less specific one doesn't. `becomes` is what new values have to satisfy only when `moves` is set, else it's the `scope`, and `{}` lets a record be moved out of reach. `names` are the fields that can be read or written, none meaning all.
- **The policy models aren't `Secure`**, which is how a policy reads its own rules. Who may change them is up to the app.
- **Rules are looked up once** for as long as the actor is acting.

**Status:** scaffold. See the first ticket for the design and what done looks like.
