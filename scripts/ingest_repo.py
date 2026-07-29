import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from db.models import Node, Edge, Repository
from db.session import SessionLocal
from parser.walker import walk_repo
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError


def merge_fragment_nodes(session, repo_id: int):
    fragments = session.query(Node).filter_by(
        repo_id=repo_id, file_path=None
    ).all()

    merged_count = 0
    skipped_ambiguous = 0

    for fragment in fragments:
        candidates = session.query(Node).filter(
            Node.repo_id == repo_id,
            Node.name == fragment.name,
            Node.file_path.isnot(None)
        ).all()

        if len(candidates) != 1:
            skipped_ambiguous += 1
            continue

        true_def = candidates[0]

        outgoing = session.query(Edge).filter_by(repo_id=repo_id, caller_id=fragment.id).all()
        for edge in outgoing:
            duplicate = session.query(Edge).filter_by(
                repo_id=repo_id, caller_id=true_def.id, callee_id=edge.callee_id
            ).first()
            if duplicate:
                session.delete(edge)  # redirect would collide — drop the redundant one
            else:
                edge.caller_id = true_def.id

        incoming = session.query(Edge).filter_by(repo_id=repo_id, callee_id=fragment.id).all()
        for edge in incoming:
            duplicate = session.query(Edge).filter_by(
                repo_id=repo_id, caller_id=edge.caller_id, callee_id=true_def.id
            ).first()
            if duplicate:
                session.delete(edge)
            else:
                edge.callee_id = true_def.id

        session.flush()  
        session.delete(fragment)
        merged_count += 1

    session.commit()
    print(f"Merge pass: {merged_count} fragments merged, {skipped_ambiguous} skipped (ambiguous).")


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
    # Insert nodes using INSERT ... ON CONFLICT DO NOTHING RETURNING id
    for (name, file_path, is_external) in unique_nodes:
        stmt = insert(Node).values(
            name=name,
            file_path=file_path,
            is_external=is_external,
            repo_id=repo_id,
        ).on_conflict_do_nothing().returning(Node.id)
        res = session.execute(stmt)
        row = res.fetchone()
        if row and row[0]:
            node_id_map[(name, file_path)] = row[0]
        else:
            existing = session.query(Node).filter_by(
                name=name, file_path=file_path, repo_id=repo_id
            ).first()
            if existing:
                node_id_map[(name, file_path)] = existing.id
            else:
                # As a fallback, create the node and commit so subsequent edges can reference it
                node = Node(name=name, file_path=file_path, is_external=is_external, repo_id=repo_id)
                session.add(node)
                session.flush()
                node_id_map[(name, file_path)] = node.id

    # Persist nodes before inserting edges to satisfy foreign key constraints
    session.commit()

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
    merge_fragment_nodes(session, repo_id)
    session.close()
    print(f"Done — {len(unique_nodes)} nodes, {len(edges)} edges ingested.")

from parser.walker import walk_repo
edges = walk_repo(r"C:\Users\laksh\OneDrive\Desktop\Programs\Python\insightforge\app")
print(len(edges))

if __name__ == "__main__":
    ingest(sys.argv[1], sys.argv[2], sys.argv[3])



