import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from db.session import SessionLocal
import networkx as nx
from db.models import Node,Edge


graph_cache = {}  

def get_graph(repo_id: int) -> nx.DiGraph:
    if repo_id not in graph_cache:
        graph_cache[repo_id] = load_graph_from_db(repo_id)
    return graph_cache[repo_id]


def load_graph_from_db(repo_id:int) -> nx.DiGraph:
    session = SessionLocal()

    G = nx.DiGraph()

    for node in session.query(Node).filter_by(repo_id=repo_id).all():
        G.add_node(node.id, name=node.name, file_path=node.file_path, is_external=node.is_external)
    for edge in session.query(Edge).filter_by(repo_id=repo_id).all():
        G.add_edge(edge.caller_id, edge.callee_id, resolved = edge.resolved, is_external = edge.is_external)

    session.close()
    return G

def get_descendants(G: nx.DiGraph, node_key: int, hops: int = 3) -> nx.DiGraph:
    return nx.ego_graph(G, node_key, radius=hops, undirected=False)

def get_ancestors(G: nx.DiGraph, node_key: int, hops: int = 3) -> nx.DiGraph:
    sub = nx.ego_graph(G.reverse(), node_key, radius=hops, undirected=False)
    return sub.reverse()
    

