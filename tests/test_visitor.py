"""
Regression tests for parser/visitor.py.

Each test uses a hand-traced, known-correct expected output.
These were verified manually during development 
Run with: pytest tests/test_visitor.py -v
"""
import ast
import pytest
from parser.visitor import get_dotted_chain, collect_defined_names, CallGraphVisitor


# ------------------------------------------------------------------
# get_dotted_chain tests
# ------------------------------------------------------------------

def parse_call_func(expr: str):
    """Helper: parse a bare call expression and return its .func node."""
    tree = ast.parse(expr)
    return tree.body[0].value.func


def test_dotted_chain_clean_self():
    """self.db.execute resolves cleanly."""
    func = parse_call_func("self.db.execute(x)")
    resolved, name = get_dotted_chain(func)
    assert resolved is True
    assert name == "self.db.execute"


def test_dotted_chain_plain_name():
    """A bare function call with no dots resolves cleanly."""
    func = parse_call_func("categorize(x)")
    resolved, name = get_dotted_chain(func)
    assert resolved is True
    assert name == "categorize"


def test_dotted_chain_broken_on_call():
    """select(Report).where(x) — chain breaks on a Call node, returns partial."""
    func = parse_call_func("select(Report).where(x)")
    resolved, name = get_dotted_chain(func)
    assert resolved is False
    assert name == "where"


def test_dotted_chain_broken_on_subscript():
    """handlers['default'].process() — chain breaks on a Subscript, returns partial."""
    func = parse_call_func("handlers['default'].process()")
    resolved, name = get_dotted_chain(func)
    assert resolved is False
    assert name == "process"


def test_dotted_chain_two_dots():
    """result.scalar_one_or_none resolves cleanly — two-segment chain."""
    func = parse_call_func("result.scalar_one_or_none()")
    resolved, name = get_dotted_chain(func)
    assert resolved is True
    assert name == "result.scalar_one_or_none"


# ------------------------------------------------------------------
# CallGraphVisitor — caller attribution
# ------------------------------------------------------------------

def run_visitor(source: str):
    tree = ast.parse(source)
    defined = collect_defined_names(tree)
    v = CallGraphVisitor(defined)
    v.visit(tree)
    return v.edges


def test_basic_caller_attribution():
    """Calls inside a function get attributed to that function."""
    source = """
def process(df):
    cleaned = clean_data(df)
    return categorize(cleaned)
"""
    edges = run_visitor(source)
    callers = [e[0] for e in edges]
    assert all(c == "process" for c in callers)
    callees = [e[1] for e in edges]
    assert "clean_data" in callees
    assert "categorize" in callees


def test_async_function_attributed():
    """Async functions are tracked the same as sync ones."""
    source = """
async def fetch(session):
    result = await session.get(url)
    return result
"""
    edges = run_visitor(source)
    assert any(e[0] == "fetch" for e in edges)


def test_class_qualified_caller():
    """Methods inside a class produce ClassName.method_name as caller."""
    source = """
class MyRepo:
    def get(self):
        return self.db.execute(query)
"""
    edges = run_visitor(source)
    assert edges[0][0] == "MyRepo.get"


def test_self_calls_are_internal():
    """Calls via self.* are classified as internal (is_external=False)."""
    source = """
class Svc:
    def run(self):
        self.save()
"""
    edges = run_visitor(source)
    assert edges[0][3] is False   # is_external


def test_external_call_flagged():
    """Calls to unknown names are classified as external."""
    source = """
def process(df):
    result = some_library_func(df)
"""
    edges = run_visitor(source)
    assert edges[0][3] is True   # is_external


def test_same_file_function_is_internal():
    """A call to a function defined in the same file is internal."""
    source = """
def helper(x):
    return x

def main():
    helper(1)
"""
    edges = run_visitor(source)
    main_edges = [e for e in edges if e[0] == "main"]
    assert main_edges[0][1] == "helper"
    assert main_edges[0][3] is False   # is_external


def test_local_variable_externality_propagated():
    """
    query = select(...)   →  local_symbols['query'] = True (external)
    query.where(...)      →  is_external=True, even though chain resolves.

    This is the key regression for the query.where false-positive bug.
    """
    source = """
def get_by_id(self, id):
    query = select(Model)
    result = self.db.execute(query.where(Model.id == id))
    return result
"""
    edges = run_visitor(source)
    # Find the query.where edge
    query_where_edges = [e for e in edges if "where" in e[1]]
    assert len(query_where_edges) > 0
    for edge in query_where_edges:
        assert edge[3] is True   # is_external — query came from external select()


def test_two_functions_attributed_separately():
    """Calls in two different functions don't bleed across."""
    source = """
def a():
    foo()

def b():
    bar()
"""
    edges = run_visitor(source)
    a_edges = [e for e in edges if e[0] == "a"]
    b_edges = [e for e in edges if e[0] == "b"]
    assert all(e[1] == "foo" for e in a_edges)
    assert all(e[1] == "bar" for e in b_edges)


def test_nested_class_resets_correctly():
    """After a nested class, current_class resets to outer scope (None for module level)."""
    source = """
class Inner:
    def method(self):
        self.do_thing()

def outer():
    pass
"""
    edges = run_visitor(source)
    assert edges[0][0] == "Inner.method"