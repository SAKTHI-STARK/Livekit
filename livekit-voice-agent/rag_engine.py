import os
import asyncio
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from llama_index.core import (
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.core.schema import NodeWithScore


# CONFIGURATION SECTION

# --- Directories ---
THIS_DIR = Path(__file__).parent
DATA_DIR = THIS_DIR / "data"
PERSIST_DIR = THIS_DIR / "query-engine-storage"
ENV_PATH = THIS_DIR / ".env.local"

# --- Load Environment Variables ---
load_dotenv(dotenv_path=ENV_PATH)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env.local")

EMBED_MODEL_NAME = "models/embedding-001"

RAG_SETTINGS = {
    "top_k": 3,             # number of chunks to retrieve
    "snippet_length": 200,  # max chars per snippet
    "min_score_threshold": 0.0,  # filter out weak matches if needed
}


# INDEX INITIALIZATION
def build_or_load_index() -> VectorStoreIndex:
    """Load existing index or create a new one from documents."""
    if not PERSIST_DIR.exists():
        print("Creating new vector index...")
        if not DATA_DIR.exists() or not any(DATA_DIR.iterdir()):
            raise FileNotFoundError(f"No documents found in {DATA_DIR}")

        documents = SimpleDirectoryReader(DATA_DIR).load_data()
        index = VectorStoreIndex.from_documents(
            documents,
            embed_model=GeminiEmbedding(
                model_name=EMBED_MODEL_NAME, api_key=GOOGLE_API_KEY
            ),
        )
        index.storage_context.persist(persist_dir=PERSIST_DIR)
        print(f"Index created and saved at {PERSIST_DIR}")
    else:
        print("Loading existing vector index...")
        storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
        index = load_index_from_storage(
            storage_context,
            embed_model=GeminiEmbedding(
                model_name=EMBED_MODEL_NAME, api_key=GOOGLE_API_KEY
            ),
        )
        print("Index loaded successfully.")
    return index


# Load global index + retriever
INDEX = build_or_load_index()
RETRIEVER = INDEX.as_retriever(similarity_top_k=RAG_SETTINGS["top_k"])


# CORE RAG FUNCTIONS

def extract_snippet(text: str, max_chars: int) -> str:
    """Return a trimmed snippet of the content."""
    text = text.strip()
    return text if len(text) <= max_chars else text[:max_chars] + "..."


async def query_info(query: str, top_k: int | None = None) -> str:
    top_k = top_k or RAG_SETTINGS["top_k"]
    RETRIEVER.similarity_top_k = top_k
    nodes: List[NodeWithScore] = await RETRIEVER.aretrieve(query)

    if not nodes:
        return "No relevant information found."

    results = []
    for i, node in enumerate(nodes, start=1):
        if node.score < RAG_SETTINGS["min_score_threshold"]:
            continue
        text = extract_snippet(node.get_content(), RAG_SETTINGS["snippet_length"])
        file_name = Path(node.metadata.get("file_path", "unknown")).name
        results.append(f"[{i}] ({node.score:.4f}) {file_name}:\n{text}\n")

    if not results:
        return "No high-confidence results found."
    return "\n" + ("-" * 60) + "\n".join(results)


def query_info_sync(query: str, top_k: int | None = None) -> str:
    try:
        return asyncio.run(query_info(query, top_k))
    except RuntimeError:
        import nest_asyncio
        nest_asyncio.apply()
        return asyncio.run(query_info(query, top_k))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Query local RAG knowledge base.")
    parser.add_argument("query", nargs="?", help="Your query text.")
    parser.add_argument("--top-k", type=int, default=RAG_SETTINGS["top_k"], help="Number of results.")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run interactive mode.")
    args = parser.parse_args()

    if args.interactive:
        print("Interactive mode — type your query ('exit' to quit)\n")
        while True:
            try:
                q = input("Query: ").strip()
                if q.lower() in {"exit", "quit", "q"}:
                    print("Goodbye!")
                    break
                if not q:
                    continue
                print(query_info_sync(q, top_k=args.top_k))
                print("\n" + "=" * 80 + "\n")
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
    else:
        if not args.query:
            print("Please provide a query or use --interactive mode.")
        else:
            print(f"\nQuery: {args.query}\n{'=' * 80}")
            print(query_info_sync(args.query, top_k=args.top_k))
            print("=" * 80)
