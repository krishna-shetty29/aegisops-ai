import hashlib
import os
from pathlib import Path

import chromadb
from google import genai
from google.genai import types


PROJECT_ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_BASE_PATH = PROJECT_ROOT / "knowledge_base"
CHROMA_PATH = PROJECT_ROOT / "data" / "chroma"


chroma_client = chromadb.PersistentClient(
    path=str(CHROMA_PATH)
)

knowledge_collection = chroma_client.get_or_create_collection(
    name="devops_knowledge",
    metadata={"hnsw:space": "cosine"},
)


def get_gemini_client():
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    if not gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY was not found in your .env file."
        )

    return genai.Client(api_key=gemini_api_key)


def create_document_embedding(text: str, title: str):
    client = get_gemini_client()

    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            title=title,
            output_dimensionality=768,
        ),
    )

    return response.embeddings[0].values


def create_query_embedding(query: str):
    client = get_gemini_client()

    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=768,
        ),
    )

    return response.embeddings[0].values


def split_into_chunks(text: str, chunk_size=1200, overlap=200):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])

        start += chunk_size - overlap

    return chunks


def add_document_to_knowledge_base(
    text: str,
    title: str,
    source: str,
    category: str,
):
    chunks = split_into_chunks(text)

    ids = []
    documents = []
    embeddings = []
    metadatas = []

    for chunk_number, chunk in enumerate(chunks):
        unique_text = f"{source}-{chunk_number}-{chunk}"

        document_id = hashlib.sha256(
            unique_text.encode("utf-8")
        ).hexdigest()

        ids.append(document_id)
        documents.append(chunk)
        embeddings.append(
            create_document_embedding(chunk, title)
        )
        metadatas.append(
            {
                "title": title,
                "source": source,
                "category": category,
                "chunk_number": chunk_number,
            }
        )

    knowledge_collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return {
        "source": source,
        "chunks_added": len(chunks),
    }


def index_knowledge_base_folder():
    if not KNOWLEDGE_BASE_PATH.exists():
        raise FileNotFoundError(
            "knowledge_base folder does not exist."
        )

    indexed_files = []
    allowed_extensions = {".md", ".txt"}

    for file_path in KNOWLEDGE_BASE_PATH.rglob("*"):
        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in allowed_extensions:
            continue

        text = file_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        if not text.strip():
            continue

        relative_path = file_path.relative_to(PROJECT_ROOT)

        result = add_document_to_knowledge_base(
            text=text,
            title=file_path.stem.replace("_", " "),
            source=str(relative_path),
            category=file_path.parent.name,
        )

        indexed_files.append(result)

    return {
        "files_indexed": len(indexed_files),
        "details": indexed_files,
    }


def search_knowledge(query: str, number_of_results=3):
    query_embedding = create_query_embedding(query)

    results = knowledge_collection.query(
        query_embeddings=[query_embedding],
        n_results=number_of_results,
        include=["documents", "metadatas", "distances"],
    )

    matches = []

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances,
    ):
        matches.append(
            {
                "text": document,
                "metadata": metadata,
                "distance": distance,
            }
        )

    return matches


def format_knowledge_context(matches: list[dict]):
    if not matches:
        return "No related knowledge was found."

    formatted_matches = []

    for number, match in enumerate(matches, start=1):
        source = match["metadata"].get("source", "Unknown source")

        formatted_matches.append(
            f"Knowledge match {number} "
            f"(source: {source}):\n"
            f"{match['text']}"
        )

    return "\n\n".join(formatted_matches)