#!/usr/bin/env python3
"""
rag_gemini_chroma.py

Builds a vector DB (Chroma) using Gemini embeddings.
Retrieves best-matching API docs based on user query.
Parses structured JSON (API details + payload + response + example).
Generates a natural-language explanation using Gemini model.
"""
import argparse
import os
import re
import ast
import json
from tqdm import tqdm
import google.generativeai as genai
from chromadb import PersistentClient
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from loguru import logger
import traceback

# ============ Logging Setup ============
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logger.add(
    os.path.join(LOG_DIR, "rag_assistant.log"),
    rotation="10 MB",
    retention="10 days",
    compression="zip",
    enqueue=True,
    backtrace=True,
    diagnose=True,
    level="INFO"
)

logger.info("🚀 RAG + Gemini Assistant started.")

def get_or_create_collection(client, name, rebuild=False):
    """
    Smart Chroma collection handler:
    - rebuild=True → delete + create new collection
    - rebuild=False → load existing collection or raise error if missing
    """
    existing_collections = [c.name for c in client.list_collections()]

    if rebuild:
        if name in existing_collections:
            logger.info(f"🧱 Rebuilding collection: {name}")
            client.delete_collection(name)
        return client.create_collection(name)

    if name in existing_collections:
        logger.info(f"✅ Using existing collection: {name}")
        return client.get_collection(name)
    else:
        logger.error(f"❌ Collection '{name}' not found. Run with --build first.")
        raise RuntimeError("No existing embeddings found. Please run with --build first.")

load_dotenv()

# ==============================
# CONFIG
# ==============================
DATA_PATH = "data/processed/tickets_static.json"
CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "freshservice_docs"
GEMINI_MODEL = "gemini-2.5-flash-lite"
EMBED_MODEL = "models/embedding-001"  # Gemini embedding model

# ==============================
# SETUP
# ==============================
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise EnvironmentError("⚠️ GEMINI_API_KEY not found. Set it before running this script.")
genai.configure(api_key=api_key)

# Initialize Chroma (lazy)
chroma_client = PersistentClient(path=CHROMA_DIR)
collection = None

def init_chroma(rebuild=False):
    global collection
    collection = get_or_create_collection(chroma_client, COLLECTION_NAME, rebuild=rebuild)
    return collection


# Embedding function using Gemini (drop sentence-transformers/tokenizers dependency)
from functools import lru_cache


def _embed_with_gemini(text: str):
    try:
        resp = genai.embed_content(model=EMBED_MODEL, content=text, task_type="RETRIEVAL_DOCUMENT")
        vec = getattr(resp, "embedding", None)
        if vec is None and isinstance(resp, dict):
            vec = resp.get("embedding")
        return list(vec) if vec is not None else []
    except Exception as e:
        logger.exception(f"❌ Gemini embedding failed: {e}")
        return []


@lru_cache(maxsize=2048)
def cached_embedding(text_hash: str, content: str):
    return _embed_with_gemini(content)


def gemini_embed(texts):
    """Local embedding with caching for faster repeated calls."""
    if isinstance(texts, list):
        texts = texts[0]
    text_hash = str(abs(hash(texts)))[:12]
    return cached_embedding(text_hash, texts)


# ==============================
# BUILD FUNCTIONS
# ==============================

def load_sections():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    sections = data.get("content_sections", [])
    if not sections:
        raise ValueError("No content_sections found in the JSON file.")
    return sections


def build_embeddings(rebuild=False):
    init_chroma(rebuild=rebuild)
    sections = load_sections()
    print(f"📦 Building ChromaDB from {len(sections)} sections...")
    for idx, sec in enumerate(tqdm(sections, desc="Embedding sections")):
        text = sec.get("text", "")
        code = "\n".join(sec.get("code_blocks", []))
        tables = json.dumps(sec.get("tables", []), ensure_ascii=False)
        content = f"{sec.get('title', '')}\n{text}\n{code}\n{tables}"
        emb = gemini_embed(content)
        doc_id = f"doc_{idx}"
        # Skip if doc already exists when not rebuilding
        try:
            existing = collection.get(ids=[doc_id])
            if existing and existing.get("ids"):
                continue
        except Exception:
            pass
        collection.add(
            ids=[doc_id],
            documents=[content],
            embeddings=[emb],
            metadatas=[{
                "id": str(sec.get("id")),
                "title": sec.get("title") or "",
                "source": sec.get("source", ""),
                "code_blocks": json.dumps(sec.get("code_blocks", []), ensure_ascii=False),
                "tables": json.dumps(sec.get("tables", []), ensure_ascii=False)
            }]
        )
    print("✅ Vector DB build completed.")

# ==============================
# HELPER FUNCTIONS
# ==============================

def parse_code_for_json(code_text):
    """Extract JSON-like content (payload or response) from code snippets."""
    json_candidates = re.findall(r'(\{[\s\S]*?\})', code_text)
    parsed = []
    for jc in json_candidates:
        try:
            obj = ast.literal_eval(jc.replace("null", "None"))
            parsed.append(obj)
        except Exception:
            pass
    return parsed

def extract_api_struct(section):
    """Parse a section dict to structured API JSON."""
    title = section.get("title", "Unknown API")
    text = section.get("text", "")
    code_blocks = section.get("code_blocks", [])
    tables = section.get("tables", [])

    endpoint_match = re.search(r"/api/v\d+/\S+", text)
    endpoint = endpoint_match.group(0) if endpoint_match else None

    request_payload, response_body = None, None
    for code in code_blocks:
        lower = code.lower()
        if "post" in lower or "request" in lower:
            jsons = parse_code_for_json(code)
            if jsons:
                request_payload = jsons[0]
        elif "response" in lower or "return" in lower:
            jsons = parse_code_for_json(code)
            if jsons:
                response_body = jsons[0]

    # Example snippet
    example = next((code for code in code_blocks if "curl" in code.lower()), None)

    return {
        "api_name": title,
        "endpoint": endpoint,
        "required_payload": request_payload or {},
        "response_body": response_body or {},
        "example": example or "",
    }

def search_query(query, top_k=3):
    """Retrieve top-k relevant sections using Chroma."""
    try:
        query_embedding = gemini_embed(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=top_k)
        docs = []
        for i in range(len(results["documents"][0])):
            docs.append({
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i]
            })
        return docs
    except Exception as e:
        logger.exception(f"❌ Vector search failed: {e}")
        return []

def ask_gemini(prompt):
    """Generate an answer using Gemini LLM with safety and retries."""
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        return response.text if hasattr(response, "text") else str(response)
    except Exception as e:
        logger.exception(f"❌ Gemini request failed: {e}")
        return "⚠️ Gemini encountered an issue generating a response."


# ==============================
# QUERY LOGIC
# ==============================
def sanitize_input(text: str) -> str:
    """Prevents malicious prompt injection and system manipulation."""
    forbidden = ["ignore previous", "delete", "shutdown", "system", "run code", "eval"]
    if any(f in text.lower() for f in forbidden):
        logger.warning(f"🚨 Unsafe input detected: {text}")
        raise ValueError("Unsafe or potentially malicious input detected.")
    return text.strip()

def clean_text(text: str):
    """Remove markdown symbols like ###, ``` and backticks from Gemini output."""
    text = re.sub(r"```[a-zA-Z]*", "", text)
    text = re.sub(r"```", "", text)
    text = re.sub(r"###", "", text)
    text = re.sub(r"\*\*", "", text)
    text = text.replace("* ", "• ")
    return text.strip()

def query_api(question):
    question = sanitize_input(question)
    print(f"\n🔍 Query: {question}\n")
    retrieved = search_query(question, top_k=3)

    structured = []
    for r in retrieved:
        section = {
            "title": r["metadata"]["title"],
            "text": r["text"],
            "code_blocks": json.loads(r["metadata"]["code_blocks"]),
            "tables": json.loads(r["metadata"]["tables"])
        }
        structured.append(extract_api_struct(section))

    # Build Gemini context
    context = "\n\n".join([
        f"API: {s['api_name']}\nEndpoint: {s['endpoint']}\nExample: {s['example']}"
        for s in structured
    ])

    prompt = f"""
You are a professional API assistant for Freshservice developers.
Answer the question clearly and professionally.
Explain endpoint, required payload, response format, and example.
Avoid markdown syntax like ### or ``` in the answer.

Context:
{context}

Question:
{question}
"""
    answer = ask_gemini(prompt)
    clean_answer = clean_text(answer)

    # 🖨️ Pretty CLI Output
    print("\n────────────────────────────────────────────")
    print(f"🔍 Query: {question}")
    print("────────────────────────────────────────────\n")

    print("🧠 Gemini Answer:")
    print(clean_answer, "\n")

    for match in structured:
        print(f"📘 API Name: {match['api_name']}")
        if match['endpoint']:
            print(f"📤 Endpoint: {match['endpoint']}")
        if match['required_payload']:
            print("📦 Required Payload:")
            print(json.dumps(match['required_payload'], indent=2, ensure_ascii=False))
        if match['response_body']:
            print("✅ Response Body:")
            print(json.dumps(match['response_body'], indent=2, ensure_ascii=False))
        if match['example']:
            print("💻 Example:")
            print(match['example'])
        print("────────────────────────────────────────────")

    return {
        "query": question,
        "matches": structured,
        "gemini_answer": clean_answer
    }

# ==============================
# MAIN EXECUTION
# ==============================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG + Gemini Assistant")
    parser.add_argument("--build", action="store_true", help="Build ChromaDB embeddings")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild collection from scratch")
    parser.add_argument("--query", action="store_true", help="Run interactive Gemini Q&A")
    args = parser.parse_args()

    if args.build:
        logger.info("🔧 Running in BUILD mode...")
        try:
            build_embeddings(rebuild=args.rebuild)
            logger.success("✅ Embedding build completed successfully.")
        except Exception as e:
            logger.exception(f"❌ Build failed: {e}")
    elif args.query:
        logger.info("💬 Running in QUERY mode...")
        init_chroma(rebuild=False)
        while True:
            q = input("\n💬 Enter your question (or 'exit'): ").strip()
            if q.lower() in ["exit", "quit"]:
                logger.info("👋 Session ended by user.")
                break
            try:
                query_api(q)
            except Exception as e:
                logger.exception(f"❌ Query failed: {e}")
    else:
        parser.print_help()