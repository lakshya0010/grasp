import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from db.session import SessionLocal
import networkx as nx
from db.models import Node,Edge

def load_graph_from_db() -> nx.DiGraph:
    session = SessionLocal()

    G = nx.DiGraph()

    for node in session.query(Node).all():
        G.add_node(node.id, name=node.name, file_path=node.file_path, is_external=node.is_external)
    for edge in session.query(Edge).all():
        G.add_edge(edge.caller_id, edge.callee_id, resolved = edge.resolved, is_external = edge.is_external)

    session.close()
    return G

def get_descendants(G: nx.DiGraph, node_key: int, hops: int = 3) -> nx.DiGraph:
    return nx.ego_graph(G, node_key, radius=hops, undirected=False)

def get_ancestors(G: nx.DiGraph, node_key: int, hops: int = 3) -> nx.DiGraph:
    return nx.ego_graph(G.reverse(), node_key, radius=hops, undirected=False)
    

G = load_graph_from_db()
print(G.number_of_nodes())
print(G.number_of_edges())

G = load_graph_from_db()

# look up node id for StatementService.upload_statement
session = SessionLocal()
node = session.query(Node).filter_by(name="self.get_by_id").first()
session.close()

sub = get_ancestors(G, node.id, hops=2)
for n in sub.nodes(data=True):
    print(n)