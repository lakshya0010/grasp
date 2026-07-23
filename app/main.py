import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import networkx as nx
from typing import Optional
import shutil

from parser.clone import clone_repo
from app.reasoning import ask_llm
from db.session import SessionLocal
from db.models import Node,Repository
from parser.graph import load_graph_from_db, get_ancestors, get_descendants, graph_cache, get_graph
from scripts.ingest_repo import ingest
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class IngestRequest(BaseModel):
    repo_path: Optional[str] = None
    repo_name: str
    repo_url: Optional[str] = None

class QueryRequest(BaseModel):
    repo_id: int
    node_name: str
    question: str
    hops: int = 3

@app.get("/repositories")
def list_repositories():
    session = SessionLocal()
    repos = session.query(Repository).all()
    result = [{"id":r.id, "name": r.name, "url": r.url} for r in repos]
    session.close()
    return result

@app.get("/repositories/lookup")
def lookup_repository(query: str):
    query = query.strip()
    session = SessionLocal()
    repo = session.query(Repository).filter(
        (Repository.name == query) | (Repository.url == query)
    ).first()
    session.close()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return {"id": repo.id, "name": repo.name, "url": repo.url}

@app.post("/ingest")
def ingest_repo(request: IngestRequest):
    if not request.repo_path and not request.repo_url:
        raise HTTPException(status_code=400, detail="Provide either repo_path or repo_url")

    cloned_temp_dir = None
    try:
        if request.repo_path:
            path_to_ingest = request.repo_path
        else:
            cloned_temp_dir = clone_repo(request.repo_url)
            path_to_ingest = cloned_temp_dir

        url = request.repo_url or request.repo_path
        ingest(path_to_ingest, request.repo_name, url)

    finally:
        if cloned_temp_dir:
            shutil.rmtree(cloned_temp_dir, ignore_errors=True)

    session = SessionLocal()
    repo = session.query(Repository).filter_by(name=request.repo_name).first()
    session.close()
    if repo and repo.id in graph_cache:
        del graph_cache[repo.id]
    
    return{"status": "ingested", "repo": request.repo_name, "id": repo.id}


@app.get("/graph/{repo_id}")
def get_full_graph(repo_id:int):
    G = get_graph(repo_id=repo_id)
    nodes_data = [
        {
            "id": n,
            "name": G.nodes[n]["name"],
            "file_path": G.nodes[n]["file_path"],
            "is_external": G.nodes[n]["is_external"]
        }
        for n in G.nodes
    ]
    edges_data = [
        {
            "caller_id": u,
            "callee_id": v,
            "caller": G.nodes[u]["name"],
            "callee": G.nodes[v]["name"],
            "resolved":G.edges[u,v]["resolved"],
            "is_external": G.edges[u,v]["is_external"],
        } for u,v in G.edges
    ]
    graph_data = {"nodes": nodes_data, "edges": edges_data}
    return{
        "repo_id": repo_id,
        "graph_data": graph_data
    }

@app.post("/query")
def query(request: QueryRequest):
    session = SessionLocal()
    node = session.query(Node).filter_by(
    name=request.node_name,
    repo_id=request.repo_id
    ).filter(Node.file_path.isnot(None)).first()

    if not node:
        # fallback: no defined node with this name, use whatever exists (external/call-site only)
        node = session.query(Node).filter_by(
            name=request.node_name,
            repo_id=request.repo_id
        ).first()
    if not node:
        raise HTTPException(
            status_code=404,
            detail=f"Node '{request.node_name}' not found in repo {request.repo_id}"
        )
    
    G = get_graph(repo_id=request.repo_id)

    descendants = get_descendants(G, node.id, hops=request.hops)
    ancestors = get_ancestors(G, node.id, hops=request.hops)
    combined = nx.compose(descendants, ancestors)

    nodes_data = [
        {
            "id":n,
            "name": combined.nodes[n]["name"],
            "file_path": combined.nodes[n]["file_path"],
            "is_external": combined.nodes[n]["is_external"],
        } 
        for n in combined.nodes

    ]
    edges_data = [
        {
            "caller_id": u,
            "callee_id": v,
            "caller":combined.nodes[u]["name"],
            "callee":combined.nodes[v]["name"],
            "resolved":combined.edges[u,v]["resolved"],
            "is_external": combined.edges[u,v]["is_external"],
        }
        for u,v in combined.edges
    ]
    subgraph_data = {"nodes": nodes_data, "edges": edges_data}
    answer = ask_llm(request.node_name, request.question, subgraph_data)

    return{
        "node": request.node_name,
        "question": request.question,
        "answer": answer,
        "subgraph": subgraph_data
    }

