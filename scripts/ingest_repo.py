import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from db.models import Node, Edge
from db.session import SessionLocal
from parser.walker import walk_repo


def ingest(repo_path):
    edges = walk_repo(repo_path)

    session = SessionLocal()
    unique_nodes = {}
    for edge in edges:
        caller_full, callee, resolved, is_external = edge
        file_path, caller_name = caller_full.split(":", maxsplit=1)

        unique_nodes[(caller_name, file_path, False)] = None
        unique_nodes[(callee, None, is_external)] = None

    node_id_map = {}
    for(name, file_path, is_external) in unique_nodes:
        existing = session.query(Node).filter_by(
            name=name, file_path=file_path
        ).first()
        if existing:
            node_id_map[(name, file_path)] = existing.id
        else:
            node = Node(name=name, file_path=file_path, is_external=is_external)
            session.add(node)
            session.flush()
            node_id_map[(name, file_path)] = node.id

    for edge in edges:
        caller_full, callee, resolved, is_external = edge
        file_path, caller_name = caller_full.split(":", maxsplit=1)

        caller_id = node_id_map[(caller_name, file_path)]
        callee_id = node_id_map[(callee, None)]

        edge_row = Edge(
            caller_id=caller_id,
            callee_id=callee_id,
            resolved=resolved,
            is_external=is_external,
        )
        session.add(edge_row)

    session.commit()
    session.close()
    print(f"Done — {len(unique_nodes)} nodes, {len(edges)} edges ingested.")

if __name__ == "__main__":
    ingest(sys.argv[1])



