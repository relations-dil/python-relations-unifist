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

**Status:** scaffold. See the first ticket for the design and what done looks like.
