from langchain_google_genai import ChatGoogleGenerativeAI

def build_context_string(subgraph_data:dict, node_name:str)->str:
    nodes = subgraph_data["nodes"]
    edges = subgraph_data["edges"]

    calls = []
    called_by = []
    for edge in edges:
        if edge["caller"] == node_name:
            tag = "external" if edge["is_external"] else "internal"
            calls.append(f"{edge['callee']} ({tag})")
        if edge["callee"] == node_name:
            called_by.append(edge["caller"])
    
    lines = [f"Function: {node_name}"]
    if calls:
        lines.append("This function calls: " + ", ".join(calls))
    else:
        lines.append("This function makes no further calls in the analyzed scope.")

    if called_by:
        lines.append("This function is called by: " + ", ".join(called_by))
    else:
        lines.append("No callers found in the analyzed scope.")

    return "\n".join(lines)


def ask_llm(node_name: str, question: str, subgraph_data: dict)->str:
    context = build_context_string(subgraph_data, node_name)

    prompt = f"""You are analyzing the structure of a codebase using a call graph.
Each call is tagged "internal" (defined in this codebase) or "external" (a library/stdlib call).

{context}

Question: {question}

Answer using only the structural information above. Be concise and specific.
If the information above doesn't fully answer the question, say what's missing rather than guessing.
"""
    
    llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0)
    response = llm.invoke(prompt)
    return response.content[0]["text"]