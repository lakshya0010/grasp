import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import networkx as nx

from db.session import SessionLocal
from db.models import Node
from parser.graph import load_graph_from_db, get_ancestors, get_descendants

app = FastAPI()

G = load_graph_from_db()



