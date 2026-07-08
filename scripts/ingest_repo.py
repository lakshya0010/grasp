import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from db.models import Node, Edge, Repository
from db.session import SessionLocal
from parser.walker import walk_repo
from sqlalchemy.dialects.postgresql import insert

def ingest(repo_path:str, repo_name:str, repo_url:str):
    edges = walk_repo(repo_path)

    session = SessionLocal()

    existing_repo = session.query(Repository).filter_by(url=repo_url).first()
    if existing_repo:
        repo_id = existing_repo.id
        existing_repo.name = repo_name  # allow name updates on refresh
        session.query(Edge).filter_by(repo_id=repo_id).delete()
        session.query(Node).filter_by(repo_id=repo_id).delete()
        session.commit()
    else:
        repo = Repository(name=repo_name, url=repo_url)
        session.add(repo)
        session.flush()
        repo_id = repo.id


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
            node = Node(name=name, file_path=file_path, is_external=is_external, repo_id=repo_id)
            session.add(node)
            session.flush()
            node_id_map[(name, file_path)] = node.id

    for edge in edges:
        caller_full, callee, resolved, is_external = edge
        file_path, caller_name = caller_full.split(":", maxsplit=1)
        caller_id = node_id_map[(caller_name, file_path)]
        callee_id = node_id_map[(callee, None)]

        stmt = insert(Edge).values(
            caller_id=caller_id,
            callee_id=callee_id,
            resolved=resolved,
            is_external=is_external,
            repo_id=repo_id
        ).on_conflict_do_nothing()
        session.execute(stmt)

    session.commit()
    session.close()
    print(f"Done — {len(unique_nodes)} nodes, {len(edges)} edges ingested.")

from parser.walker import walk_repo
edges = walk_repo(r"C:\Users\laksh\OneDrive\Desktop\Programs\Python\insightforge\app")
print(len(edges))

if __name__ == "__main__":
    ingest(sys.argv[1], sys.argv[2], sys.argv[3])



