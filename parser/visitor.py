import ast

def get_dotted_chain(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        parts.reverse()
        tup = (True, ".".join(parts))
        return tup
    else:
        parts.reverse()
        tup = (False, ".".join(parts))
        return tup


def collect_defined_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names
    
class CallGraphVisitor(ast.NodeVisitor):
    def __init__(self, locally_defined_names):
        self.current_class = None
        self.current_function = None
        self.local_symbols = {}
        self.locally_defined_names = locally_defined_names
        self.edges = []

    def _is_external(self, dotted_name):
        if not dotted_name:
            return True
        first_segment = dotted_name.split(".")[0]
        if first_segment == "self":
            return False
        if first_segment in self.locally_defined_names:
            return False
        if first_segment in self.local_symbols:
            return self.local_symbols[first_segment]
        return True
    

    def _qualified_name(self):
        if self.current_class is not None:
            return self.current_class + "." + self.current_function
        else:
            return self.current_function
        

    def visit_ClassDef(self, node):
        previous_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = previous_class


    def _visit_function(self, node):
        previous_function = self.current_function
        previous_symbols = self.local_symbols
        self.current_function = node.name
        self.local_symbols = {}
        self.generic_visit(node)
        self.current_function = previous_function
        self.local_symbols = previous_symbols
    
    def visit_AsyncFunctionDef(self, node):
        self._visit_function(node)
    def visit_FunctionDef(self, node):
        self._visit_function(node)


    def visit_Assign(self, node):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Call):
            var_name = node.targets[0].id
            _, base = get_dotted_chain(node.value.func)
            self.local_symbols[var_name] = self._is_external(base)
        self.generic_visit(node)


    def visit_Call(self, node):
        resolved, callee= get_dotted_chain(node.func)
        is_external = self._is_external(callee)
        if self.current_function is not None:
            caller = self._qualified_name()
            self.edges.append((caller, callee, resolved, is_external))
        self.generic_visit(node)


    
with open(r"C:\Users\laksh\OneDrive\Desktop\Programs\Python\insightforge\app\repositories\statement_repo.py") as f:
    source = f.read()
tree = ast.parse(source)
defined_names = collect_defined_names(tree)
visitor = CallGraphVisitor(defined_names)
visitor.visit(tree)
for edge in visitor.edges:
    print(edge)