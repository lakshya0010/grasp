# Grasp

**A codebase-understanding agent.** Point it at a Python repository and it builds a real, function-level call graph — parsed with Python's own `ast` module, persisted in Postgres, and explorable as an interactive graph in the browser. Click any function, ask a question, and get an answer grounded in actual graph traversal — not a guess from an LLM skimming raw source code.

Live demo: `https://grasp-frontend-eight.vercel.app`
Backend API: `https://grasp-afo3.onrender.com/docs`

---

## Why this exists

Most "AI code assistant" side projects are thin wrappers: dump a repo into an LLM's context window and hope it says something useful. That's not engineering, it's prompt-and-pray, and it doesn't scale past a few files before the model starts hallucinating structure it never actually saw.

Grasp takes the opposite approach. The graph-building and subgraph-retrieval logic is the real engineering here — it's the majority of the codebase, it's fully testable, and it works with **zero LLM involvement**. You can ask Postgres directly "what calls this function" and get a correct answer from pure graph traversal. The LLM's only job, at the very end of the pipeline, is to take that already-correct structural data and phrase it as a readable sentence. If you deleted the Gemini integration entirely, the graph would still be a complete, useful, queryable thing on its own.

That distinction — LLM as the thinnest possible layer, graph as the real product — was the non-negotiable design constraint for this whole project, and every architectural decision below was made in service of it.

---

## What it actually does

1. **Parse** — feed it a local path or a GitHub URL. Grasp clones/reads the repo, walks every `.py` file, and uses Python's `ast` module to extract every function and method definition, plus every call made from inside them.
2. **Resolve** — calls aren't always simple. `self.db.execute(x)`, `select(Report).where(...)`, calls through local variables, calls to functions imported from another file — each of these gets walked, resolved where possible, and honestly flagged as unresolved where it can't be (rather than silently guessing).
3. **Persist** — the result is a directed graph: nodes are functions/methods, edges are "this calls that." Stored in Postgres with full multi-repo isolation, so multiple codebases can live in the same database without colliding.
4. **Traverse** — loaded into `networkx` at query time. Given any function, you can ask "what does this call" (descendants) or "what calls this" (ancestors) within N hops, using real graph algorithms — no LLM needed for this step, ever.
5. **Reason** — only the small, relevant subgraph around the function in question gets handed to Gemini, along with the user's question. The model reasons over structured facts it's given, not raw code it has to interpret from scratch.
6. **Visualize** — the graph renders interactively in the browser (React + react-flow), laid out automatically with `dagre`, color-coded by internal vs. external dependencies, clickable, with a live question panel per node.

---

## Architecture

```
Python source files
        │
        ▼
   AST parser (ast module + networkx)
        │
        ▼
 Call graph edges: (caller, callee, resolved?, external?)
        │
        ▼
      Postgres  (nodes, edges, repositories — multi-tenant by repo)
        │
        ▼
  networkx DiGraph, loaded per repo, cached in memory
        │
        ▼
 Subgraph retrieval (ancestors / descendants, N-hop traversal)
        │
        ▼
   Gemini (via LangChain) — reasons over the subgraph only
        │
        ▼
 React + react-flow frontend — interactive graph, click-to-ask
```

**Backend:** Python, FastAPI, PostgreSQL (via Neon), SQLAlchemy 2.0, Alembic, `networkx`, `gitpython`
**LLM:** Gemini (`gemini-3.1-flash-lite`) via `langchain-google-genai`
**Frontend:** React, Vite, `@xyflow/react` (react-flow), `@dagrejs/dagre` for auto-layout
**Deployment:** Neon (Postgres) + Render (backend) + Vercel (frontend)

---

## The parser — where the real work happened

The core of this project is `parser/visitor.py`'s `CallGraphVisitor`, a subclass of `ast.NodeVisitor`. A few things it had to get right that a naive implementation wouldn't:

- **Caller attribution requires state, not just tree-walking.** A flat `ast.walk()` finds every `Call` node in a file but loses all context about *which function* each call happened inside. The visitor threads `current_function` and `current_class` through the recursion (saved and restored around each `FunctionDef`/`ClassDef`), so every call gets correctly attributed to its enclosing method — including through nested functions and nested classes, which Python's own call stack handles for free once you structure the save/restore correctly.

- **Dotted call chains aren't one node — they're nested `Attribute` objects.** `self.db.execute(x)` isn't a single AST node with the string `"self.db.execute"` sitting in it; it's three layers of `Attribute` wrapping a `Name`, and you have to walk down to the bottom and reverse-assemble the pieces. Chains that hit a `Call` mid-walk (`select(Report).where(...)`) or a `Subscript` (`handlers['default'].process()`) can't be fully resolved statically — the parser detects this and returns a `resolved: False` flag with whatever partial name it managed to extract, rather than either crashing or silently lying about confidence.

- **Internal vs. external classification uses real import resolution, not guesswork.** A call is internal if it's `self.*`, matches a function defined in the same file, or matches an entry in that file's import table whose source module falls under the repo's own package namespace (checked against every file the repo walker actually found — not hardcoded to any one project's folder structure). Everything else — stdlib, third-party libraries, genuinely external calls — is flagged external.

- **Local variable reassignment is tracked, narrowly.** `query = select(...)` followed by `query.where(...)` used to produce a confident-looking but wrong answer: the resolver would happily report `query.where` as a clean, resolved, internal-looking call, when really `query` was assigned from an external SQLAlchemy call. The visitor now tracks a small per-function symbol table (`{variable_name: was_this_external}`) and propagates that status forward through simple reassignment — enough to catch the common case without attempting full data-flow analysis, which would be a much bigger and different project.

- **Cross-file node fragmentation gets merged after ingestion.** A function called by its bare name from a different file (e.g. `field_completeness_score()` called from `compute_extraction_confidence` in the same file, or `self.repo.get_by_id()` called from a service layer elsewhere) initially produces a separate "fragment" node with no file path — disconnected from the real definition node. A post-ingestion merge pass finds fragments that match exactly one real definition by name, redirects every edge pointing at the fragment to point at the true definition instead, and removes the fragment. Ambiguous cases (two or more same-named candidates across different files) are deliberately left unmerged rather than guessed — a wrong merge is worse than no merge.

---

## Known limitations (deliberate, not accidental)

Every one of these was found through actual testing against real repositories, diagnosed to its root cause, and scoped out on purpose rather than left as a mystery bug:

- **Local-variable object tracing is shallow.** If `repo = self.get_repository()` and later `repo.find_by_id(x)` is called, the parser doesn't trace `repo`'s type back to know what `find_by_id` really resolves to. Full type inference is a much larger project (it's most of what real language servers exist to do) and was deliberately out of scope.
- **No class inheritance resolution.** `self.method()` is assumed to belong to the current class; inherited methods from a base class defined elsewhere aren't traced.
- **Module-level orchestration code is invisible to the graph.** Code that runs outside any function or method — for example, LangGraph's `graph.add_node("x", some_function)` pattern in a bare script file — isn't attributed to any caller, because the visitor only records calls that happen *inside* a function definition. This was discovered concretely while testing against a LangGraph-based repo, where the entire orchestration wiring file produced zero edges. It's not a bug so much as a structural boundary: call-graph analysis and data-flow/reference analysis are genuinely different problems, and this project is scoped to the former.
- **No real user authentication.** Repos aren't tied to accounts. Instead of a public list of every ingested repo (which would leak the existence and names of everyone's private codebases), the app requires knowing a repo's exact name or URL to retrieve it — closer to an unlisted link than real access control. A legitimate, deliberate scope call for a portfolio project, not a production security model.

---

## What I'd build next, given more time

- Proper multi-user auth with a `user_id` column and per-user repo isolation
- File-clustering in the graph view (collapsible groups by module) for very large repos, now that the underlying node-identity merge means clustering would organize *correct* data instead of tidying up fragments
- Broader import-pattern coverage in cross-file resolution
- A force-directed layout option (`d3-force`) as an alternative to the current hierarchical `dagre` layout — react-flow's official example for this is a paid feature, so it'd mean a from-scratch integration

---

## Running it locally

**Backend:**
```bash
cd grasp
pip install -r requirements.txt
# set DATABASE_URL and GOOGLE_API_KEY in .env
alembic upgrade head
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd grasp-frontend
npm install
# set VITE_API_URL in .env
npm run dev
```

**Ingesting a repo:**
```bash
python scripts/ingest_repo.py <path-or-github-url> <name> <url>
```
or via the running app's "Ingest a new repo" screen.

---

## A note on the build process

This project was built end-to-end from a standing start with the Python `ast` module and zero prior React/JavaScript experience — both learned specifically for this project, in parallel with the backend work. Every bug documented above (the directional bug in ancestor traversal, the node-identity fragmentation, the cross-repo node leakage in early multi-tenancy, the CORS/deployment issues in production) was found through actual testing against real code, diagnosed to a specific root cause with SQL/data evidence before being fixed — not patched blind. That process, more than the finished graph itself, is the actual point of the project.