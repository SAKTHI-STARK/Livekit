#!/usr/bin/env python3
"""
Retrieval-only RAG pipeline using LlamaIndex + Gemini embeddings.
No LLM involved — pure vector retrieval.
Persists index locally and supports async/sync queries.
"""

import os
import asyncio
import argparse
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from llama_index.core import (
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.core.schema import NodeWithScore

# === Configuration ===
THIS_DIR = Path(__file__).parent
DATA_DIR = THIS_DIR / "data"
PERSIST_DIR = THIS_DIR / "query-engine-storage"
ENV_PATH = THIS_DIR / ".env.local"

# Load environment variables
load_dotenv(dotenv_path=ENV_PATH)

# Validate API key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env.local")

# Initialize Gemini embedding model
embed_model = GoogleGenAIEmbedding(
    model_name="models/embedding-001",  # Official model name
    api_key=GOOGLE_API_KEY,
)

# === Index Management ===
def build_or_load_index() -> VectorStoreIndex:
    """Create new index from documents or load existing one."""
    if not PERSIST_DIR.exists():
        print("Creating new vector index from documents...")
        if not DATA_DIR.exists() or not any(DATA_DIR.iterdir()):
            raise FileNotFoundError(f"No documents found in {DATA_DIR}")

        documents = SimpleDirectoryReader(DATA_DIR).load_data()
        index = VectorStoreIndex.from_documents(
            documents,
            embed_model=embed_model,
        )
        index.storage_context.persist(persist_dir=PERSIST_DIR)
        print(f"Index created and persisted at: {PERSIST_DIR}")
    else:
        print("Loading existing vector index...")
        storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
        index = load_index_from_storage(
            storage_context,
            embed_model=embed_model,
        )
        print("Index loaded successfully.")

    return index


# Build/Load index
index = build_or_load_index()

# Initialize retriever
retriever = index.as_retriever(similarity_top_k=3)  # Configurable top-k


# === Query Functions ===
async def query_info(query: str, top_k: int = 3) -> str:
    """
    Retrieve top_k most relevant document chunks for the query.
    Returns formatted string with source, score, and content.
    """
    # Temporarily override top_k
    retriever.similarity_top_k = top_k
    nodes: List[NodeWithScore] = await retriever.aretrieve(query)

    if not nodes:
        return "No relevant information found."

    results = []
    for i, node in enumerate(nodes, 1):
        text = node.get_content().strip()
        score = node.score
        metadata = node.metadata
        file_name = metadata.get("file_name", "unknown")
        file_path = metadata.get("file_path", "unknown")

        results.append(
            f"Result {i} | Score: {score:.4f} | Source: {Path(file_path).name}\n"
            f"{text}\n"
        )

    return "\n{'-'*60}\n".join(results)


def query_info_sync(query: str, top_k: int = 3) -> str:
    """
    Synchronous wrapper for query_info.
    Handles nested event loops gracefully (e.g., Jupyter).
    """
    try:
        return asyncio.run(query_info(query, top_k=top_k))
    except RuntimeError as e:
        if "asyncio.run() cannot be called from a running event loop" in str(e):
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.run(query_info(query, top_k=top_k))
        raise


# === CLI Entry Point ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Query local knowledge base using Gemini embeddings (retrieval-only)."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="What is this project about?",
        help="Query string to search in documents",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of top results to return (default: 3)",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Enter interactive query mode",
    )

    args = parser.parse_args()

    if args.interactive:
        print("Interactive mode: Type your query (or 'exit' to quit)\n")
        while True:
            try:
                q = input("Query: ").strip()
                if q.lower() in {"exit", "quit", "q"}:
                    print("Goodbye!")
                    break
                if not q:
                    continue
                print("\nRetrieving...\n")
                result = query_info_sync(q, top_k=args.top_k)
                print(result)
                print("\n" + "="*80 + "\n")
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
    else:
        print(f"\nQuery: {args.query}\n")
        print("="*80)
        result = query_info_sync(args.query, top_k=args.top_k)
        print(result)
        print("="*80)