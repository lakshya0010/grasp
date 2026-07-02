# Grasp

A codebase-understanding agent. Point it at a Python repo, and it builds a
function-level call graph — stored in Postgres — that you can query and reason
over. Ask structural questions ("what breaks if I change this function?", "what
touches the DB layer?") and get answers grounded in real graph traversal, not
LLM guesswork over raw source.

**This is not an LLM wrapper.** The graph-building and subgraph-retrieval logic
is the real engineering. The LLM call (Groq) is a thin layer on top that phrases
precomputed graph results as natural language. Every structural question can be
answered by pure graph traversal with zero LLM involvement — the LLM only adds
readability.

## Stack

- **Parser:** Python `ast` module + `networkx`
- **Backend:** FastAPI + PostgreSQL + SQLAlchemy 2.0 + Alembic
- **LLM:** Groq (Llama 3.3-70b) — Week 2
- **Frontend:** React + react-flow — Week 3
- **Deployment:** Railway

## Architecture (high level)

```
Python source files
        ↓
   AST parser (parser/)
        ↓
 Call graph edges (caller, callee, resolved, is_external)
        ↓
   Postgres (nodes + edges tables)
        ↓
 Subgraph retrieval (networkx traversal)
        ↓
   Groq reasoning layer
        ↓
 React frontend (react-flow graph viz + chat interface)
```

## Project Structure

```
grasp/
├── parser/          # AST extraction — single-file and multi-file
│   ├── visitor.py   # CallGraphVisitor, get_dotted_chain, collect_defined_names
│   ├── walker.py    # Multi-file repo walker (Week 1, in progress)
│   └── models.py    # Node/Edge dataclasses
├── db/              # SQLAlchemy models + session (Week 1)
├── alembic/         # DB migrations
├── app/             # FastAPI routes (Week 2)
├── scripts/
│   └── ingest_repo.py  # CLI: parse a repo and persist to Postgres
└── tests/
    └── test_visitor.py
```

## Known Limitations (deliberate Week 1 scope boundaries)

- **Cross-file call resolution:** calls to functions defined in *other* files of
  the same repo are currently classified as `is_external=True`. Multi-file
  import-table resolution is the next implemented feature.
- **Local variable tracing:** only simple single-target assignments (`x = some_call()`)
  are tracked for externality propagation. Full data-flow analysis is out of scope.
- **No class inheritance resolution:** `self.method()` is assumed to belong to
  the current class. Inherited methods from external base classes are not traced.

## Progress Log

### Week 1 — Day 2
- `CallGraphVisitor` working on single files: class-qualified caller identity
  (`ClassName.method_name`), dotted-chain resolution with graceful failure on
  `Call`/`Subscript` chains, local-variable symbol table for externality
  propagation (fixes `query.where` false-positive), `AsyncFunctionDef` support.
- Tested on real InsightForge repository file (`statement_repository.py`).
- Regression test suite started (`tests/test_visitor.py`).