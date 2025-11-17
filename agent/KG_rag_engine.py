"""
KG-backed RAG engine used by NVExperimentAgent.

- Uses the same Postgres (pgvector) and Neo4j graph the ingestion job initializes.
- Saves new conversations into documents/chunks and appends facts to the KG.
- Runs hybrid vector search + graph search via KG.tools and returns a unified list.
"""

import os
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

# --- DB / Graph infra (same as your ingestion & tools stack) ---
# Prefer absolute-style imports from your KG package
from KG.db_utils import initialize_database, close_database, db_pool
from KG.graph_utils import initialize_graph, close_graph
from KG.ingestion.chunker import ChunkingConfig, create_chunker
from KG.ingestion.embedder import create_embedder
from KG.ingestion.graph_builder import create_graph_builder
from KG.tools import (
    VectorSearchInput, GraphSearchInput, HybridSearchInput,
    vector_search_tool, graph_search_tool, hybrid_search_tool,
    perform_comprehensive_search
)
from KG.providers import get_embedding_client, get_embedding_model

# --- Embedding provider (same as tools.py) ---
_embedding_client = get_embedding_client()
_EMBEDDING_MODEL = get_embedding_model()


def _log_to_file(log_file_path: str, role: str, content: str) -> None:
    """
    Log a message to the log file in the same format as agent.py's _log method.
    
    Args:
        log_file_path: Path to the log file
        role: Role/category of the log entry (e.g., "db_kg", "action", "rag")
        content: Content to log
    """
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {role.upper()}: {content}\n"
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        print(f"[DB/KG] Warning: Failed to log to file: {e}")

# --- Lazy singletons used by save/search ---
_INITIALIZED = False
_chunker = None
_embedder = None
_graph_builder = None


def _get_loop() -> asyncio.AbstractEventLoop:
     # Use the loop you set in the runner via asyncio.set_event_loop(loop)
     loop = asyncio.get_event_loop()
     if loop.is_closed():
         raise RuntimeError("Event loop is closed")
     return loop


async def _ensure_infra():
    global _INITIALIZED, _chunker, _embedder, _graph_builder
    if _INITIALIZED:
        return
    await initialize_database()
    await initialize_graph()
    # Minimal chunker settings for conversations
    _chunker = create_chunker(ChunkingConfig(
        chunk_size=1000, chunk_overlap=200, max_chunk_size=2000, use_semantic_splitting=True
    ))
    _embedder = create_embedder()                # same provider as ingestion
    _graph_builder = create_graph_builder()      # same KG builder as ingestion
    await _graph_builder.initialize()
    _INITIALIZED = True


# ---------------------------------------------------------------------------
# Public API (keeps your agent’s import surface identical)
# ---------------------------------------------------------------------------

def embed_text(text: str) -> List[float]:
    """Return an embedding for a short text (sync wrapper)."""
    async def _emb():
         resp = await _embedding_client.embeddings.create(model=_EMBEDDING_MODEL, input=text)
         return resp.data[0].embedding
    loop = _get_loop()
    return loop.run_until_complete(_emb())



def save_embeddings(full_text: str, json_path: str) -> None:
    """
    Compatibility: still writes a JSON file AND persists the same content into
    Postgres (documents/chunks) while appending extracted facts to the KG.
    """
    loop = _get_loop()
    loop.run_until_complete(_save_conv_into_db_and_kg(full_text, json_path))


def save_conversation_to_db_kg_only(conversation_history: List[Dict[str, str]], log_file_path: str, use_log_summary_only: bool = False) -> None:
    """
    Public function to save conversation to DB and KG only (no local embeddings directory).
    Filters out system prompts and uses LLM to summarize log files.
    
    Args:
        conversation_history: List of conversation turns with 'role' and 'content' keys
        log_file_path: Path to the log file to summarize
        use_log_summary_only: If True, use only summarized log info; if False, use filtered conversation
    """
    loop = _get_loop()
    loop.run_until_complete(_save_conv_to_db_kg_only(conversation_history, log_file_path, use_log_summary_only))



def load_embeddings(json_path: str) -> Dict[str, Any]:
    """Compatibility loader for your existing code paths."""
    if not os.path.exists(json_path):
        return {}
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)



def search_similar(query: str, embedding_file: Optional[str] = None, top_k: int = 3, use_vector: bool = True, use_graph: bool = False) -> List[Dict[str, Any]]:
    """
    Synchronous facade: run the async comprehensive search on the CURRENT loop.
    Do NOT call asyncio.run here.
    
    Args:
        query: Search query
        embedding_file: Optional embedding file (for compatibility, not used)
        top_k: Number of results to return
        use_vector: Whether to include vector search results (default: True)
        use_graph: Whether to include graph search results (default: False)
    
    Returns:
        List of search results. If both use_vector and use_graph are False, returns empty list.
    """
    # Validate that at least one search method is enabled
    if not use_vector and not use_graph:
        print("[KG_RAG] Warning: Both use_vector and use_graph are False. Returning empty results.")
        return []
    
    async def _run():
        # Call your async tools function once; it will fan-out to vector + graph safely
        res = await perform_comprehensive_search(query=query, use_vector=use_vector, use_graph=use_graph, limit=top_k)
        # Flatten to your agent's expected schema
        out: List[Dict[str, Any]] = []

        # vector results
        if use_vector:
            for r in res.get("vector_results", []):
                out.append({
                    "type": "vector",
                    "text": r.content if hasattr(r, "content") else r.get("content", ""),
                    "score": r.score if hasattr(r, "score") else r.get("score", 0.0),
                    "document_title": r.document_title if hasattr(r, "document_title") else r.get("document_title"),
                    "document_source": r.document_source if hasattr(r, "document_source") else r.get("document_source"),
                })

        # graph results
        if use_graph:
            for g in res.get("graph_results", []):
                out.append({
                    "type": "graph",
                    "text": g.fact if hasattr(g, "fact") else g.get("fact", ""),
                    "score": 1.0,   # or a heuristic
                    "title": "Knowledge Graph Fact",
                    "source": "knowledge_graph"
                })
        return out

    loop = _get_loop()
    return loop.run_until_complete(_run())

# ---------------------------------------------------------------------------
# Internal implementations (async)
# ---------------------------------------------------------------------------

async def _save_conv_into_db_and_kg(full_text: str, json_path: str) -> None:
    """Persist conversation both as a JSON file (compat) and into DB + KG."""
    await _ensure_infra()

    # 1) Keep writing the JSON file so existing agent code continues to work.
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"text": full_text, "saved_at": datetime.now().isoformat()}, f, indent=2)

    # 2) Chunk & embed (same style as ingestion, but lightweight)
    title = f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    source = "conversations/agent_cli"
    metadata = {"kind": "conversation", "ingestion_date": datetime.now().isoformat()}

    chunks = await _chunker.chunk_document(
        content=full_text, title=title, source=source, metadata=metadata
    )
    if not chunks:
        return

    embedded = await _embedder.embed_chunks(chunks)

    # 3) Save to Postgres (documents + chunks) so vector search can retrieve it later
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO documents (title, source, content, metadata)
                VALUES ($1, $2, $3, $4)
                RETURNING id::text
                """,
                title, source, full_text, json.dumps(metadata)
            )
            doc_id = row["id"]
            for ch in embedded:
                emb = '[' + ','.join(map(str, ch.embedding or [])) + ']' if getattr(ch, "embedding", None) else None
                await conn.execute(
                    """
                    INSERT INTO chunks (document_id, content, embedding, chunk_index, metadata, token_count)
                    VALUES ($1::uuid, $2, $3::vector, $4, $5, $6)
                    """,
                    doc_id, ch.content, emb, ch.index, json.dumps(ch.metadata), ch.token_count
                )

    # 4) Append facts/episodes to the SAME KG the ingestion pipeline uses
    try:
        print(f"[DB/KG] Attempting to save to knowledge graph...")
        await _graph_builder.add_document_to_graph(
            chunks=embedded,
            document_title=title,
            document_source=source,
            document_metadata=metadata
        )
        print(f"[DB/KG] Successfully saved to knowledge graph")
    except Exception as e:
        error_msg = str(e)
        if "Connection reset by peer" in error_msg or "defunct connection" in error_msg:
            print(f"[DB/KG] Neo4j connection error: {error_msg}")
            print(f"[DB/KG] This is a temporary connectivity issue. Vector database save was successful.")
        else:
            print(f"[DB/KG] Warning: Failed to save to knowledge graph: {e}")
            print(f"[DB/KG] Vector database save was successful.")
        # Don't fail the whole save on KG errors; your vector DB still has the content


async def _save_conv_to_db_kg_only(conversation_history: List[Dict[str, str]], log_file_path: str, use_log_summary_only: bool = True) -> None:
    """
    Save conversation to DB and KG only (no local embeddings directory).
    Filters out system prompts and uses LLM to summarize log files.
    
    Args:
        conversation_history: List of conversation turns
        log_file_path: Path to the log file to summarize
        use_log_summary_only: If True, use only summarized log info; if False, use filtered conversation
    """
    await _ensure_infra()

    # 1) Filter out system prompts and assistant thinking blocks
    filtered_conversation = []
    for turn in conversation_history:
        role = turn.get("role", "")
        content = turn.get("content", "")
        
        # Skip system prompts and thinking blocks
        if role == "system":
            continue
        if role == "assistant" and content.upper().startswith("(THINK)"):
            continue
        if role == "assistant" and "[Agent] WRITE DENIED" in content:
            continue
        if role == "assistant" and "[Agent] RUN DENIED" in content:
            continue
        if role == "assistant" and "[Agent] VISION DENIED" in content:
            continue
        if role == "assistant" and "[Agent] Unknown action" in content:
            continue
        # Filter out file read operations and related system messages
        if role == "assistant" and "[System] READ denied:" in content:
            continue
        if role == "assistant" and "[System] File not found:" in content:
            continue
            
        filtered_conversation.append(turn)

    if not filtered_conversation:
        print("[DB/KG] No valid conversation content to save after filtering")
        return

    # 2) Read and summarize log file using LLM
    log_summary = await _summarize_log_file(log_file_path)
    
    # 3) Choose content based on flag
    if use_log_summary_only:
        # Use only the summarized log information
        if log_summary:
            full_text = f"Log Summary: {log_summary}"
            print("[DB/KG] Using only summarized log information")
        else:
            print("[DB/KG] Warning: No log summary available, falling back to filtered conversation")
            # Fallback to filtered conversation if no summary
            conversation_text = []
            for turn in filtered_conversation:
                role = turn["role"]
                content = turn["content"]
                conversation_text.append(f"{role}: {content}")
            full_text = "\n".join(conversation_text)
    else:
        # Use filtered conversation with optional log summary
        conversation_text = []
        for turn in filtered_conversation:
            role = turn["role"]
            content = turn["content"]
            conversation_text.append(f"{role}: {content}")
        
        # Add log summary if available
        if log_summary:
            conversation_text.append(f"Log Summary: {log_summary}")
        
        full_text = "\n".join(conversation_text)
        print("[DB/KG] Using filtered conversation with log summary")

    # 4) Chunk & embed the filtered content
    title = f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    source = "conversations/agent_cli"
    metadata = {
        "kind": "conversation", 
        "ingestion_date": datetime.now().isoformat(),
        "filtered": True,
        "log_summarized": bool(log_summary),
        "log_summary_only": use_log_summary_only
    }

    chunks = await _chunker.chunk_document(
        content=full_text, title=title, source=source, metadata=metadata
    )
    if not chunks:
        return

    embedded = await _embedder.embed_chunks(chunks)

    # 5) Save to Postgres (documents + chunks) only
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO documents (title, source, content, metadata)
                VALUES ($1, $2, $3, $4)
                RETURNING id::text
                """,
                title, source, full_text, json.dumps(metadata)
            )
            doc_id = row["id"]
            for ch in embedded:
                emb = '[' + ','.join(map(str, ch.embedding or [])) + ']' if getattr(ch, "embedding", None) else None
                await conn.execute(
                    """
                    INSERT INTO chunks (document_id, content, embedding, chunk_index, metadata, token_count)
                    VALUES ($1::uuid, $2, $3::vector, $4, $5, $6)
                    """,
                    doc_id, ch.content, emb, ch.index, json.dumps(ch.metadata), ch.token_count
                )

    # 6) Append facts/episodes to the knowledge graph
    try:
        await _graph_builder.add_document_to_graph(
            chunks=embedded,
            document_title=title,
            document_source=source,
            document_metadata=metadata
        )
        print(f"[DB/KG] Successfully saved filtered conversation to database and knowledge graph")
    except Exception as e:
        print(f"[DB/KG] Warning: Failed to save to knowledge graph: {e}")
        print(f"[DB/KG] This may be due to Neo4j connectivity issues. Vector database save was successful.")
        # Don't fail the whole save on KG errors; vector DB still has the content


async def _summarize_log_file(log_file_path: str) -> str:
    """
    Use LLM to summarize the log file content using the existing chunker.
    Returns a concise summary of the log file.
    """
    if not os.path.exists(log_file_path):
        return ""
    
    print(f"[DB/KG] Summarizing log file: {os.path.basename(log_file_path)}")
    
    try:
        # Read log file
        with open(log_file_path, "r", encoding="utf-8") as f:
            log_content = f.read()
        
        # Use the existing chunker to create proper chunks
        await _ensure_infra()
        log_chunks = await _chunker.chunk_document(
            content=log_content,
            title=f"Log {os.path.basename(log_file_path)}",
            source="log_file",
            metadata={"kind": "log_summary"}
        )
        
        if not log_chunks:
            return ""
        
        # Limit to first 5 chunks to prevent token overflow
        chunks_to_process = log_chunks[:5]
        
        print(f"[DB/KG] Processing {len(chunks_to_process)} natural language chunks of log file")
        
        # Summarize each chunk
        chunk_summaries = []
        for i, chunk in enumerate(chunks_to_process):
            try:
                summary_prompt = f"""
                Please summarize this chunk of an agent log file (chunk {i+1}/{len(chunks_to_process)}). Focus on:
                1. Key user requests and agent responses
                2. Important actions taken (file reads, writes, commands run)
                3. Any errors or issues encountered
                
                Log chunk:
                {chunk.content}
                
                Provide a concise summary (max 500 words):
                """
                
                # DEBUG: Using dummy placeholder instead of actual LLM call
                # response = await _embedding_client.chat.completions.create(
                #     model="gpt-4o-mini",
                #     messages=[
                #         {"role": "system", "content": "You are a helpful assistant that summarizes log file chunks concisely. Keep summaries under 50 words."},
                #         {"role": "user", "content": summary_prompt}
                #     ],
                #     max_tokens=500,
                #     temperature=0.3
                # )
                
                # Dummy response object that matches the expected structure
                class DummyResponse:
                    class DummyChoice:
                        class DummyMessage:
                            content = f"Dummy summary for chunk {i+1} - no LLM call made for debugging"
                        message = DummyMessage()
                    choices = [DummyChoice()]
                
                response = DummyResponse()
                chunk_summary = response.choices[0].message.content.strip()
                chunk_summaries.append(f"Chunk {i+1}: {chunk_summary}")
                
            except Exception as e:
                print(f"[DB/KG] Warning: Failed to summarize chunk {i+1}: {e}")
                chunk_summaries.append(f"Chunk {i+1}: [Failed to summarize]")
        
        # Combine chunk summaries into final summary
        if chunk_summaries:
            combined_summaries = "\n".join(chunk_summaries)
            
            # Log combined summaries to the log file
            _log_to_file(log_file_path, "db_kg", f"Combined chunk summaries:\n{combined_summaries}")
            
            # Create final summary of all chunks
            final_prompt = f"""
            Please create a final summary from these log file chunk summaries. Focus on:
            1. Overall conversation flow and outcomes
            2. Key user requests and agent responses
            3. Important actions taken
            4. Any errors or issues encountered
            
            Chunk summaries:
            {combined_summaries}
            
            Provide a concise final summary (max 200 words):
            """
            
            # DEBUG: Using dummy placeholder instead of actual LLM call
            # final_response = await _embedding_client.chat.completions.create(
            #     model="gpt-4o-mini",
            #     messages=[
            #         {"role": "system", "content": "You are a helpful assistant that creates final summaries from chunk summaries. Keep summaries under 200 words."},
            #         {"role": "user", "content": final_prompt}
            #     ],
            #     max_tokens=200,
            #     temperature=0.3
            # )
            
            # Dummy response object that matches the expected structure
            class DummyFinalResponse:
                class DummyChoice:
                    class DummyMessage:
                        content = "Dummy final summary - no LLM call made for debugging. This is a placeholder response."
                    message = DummyMessage()
                choices = [DummyChoice()]
            
            final_response = DummyFinalResponse()
            return final_response.choices[0].message.content.strip()
        else:
            return ""
        
    except Exception as e:
        print(f"[DB/KG] Warning: Failed to summarize log file: {e}")
        return ""


async def _search_with_vector_and_graph(query: str, top_k: int) -> List[Dict[str, Any]]:
    """
    Use the same tools your Pydantic AI agent uses:
      - hybrid vector search (pgvector + text) for chunks
      - graph search for facts/episodes
    Then merge + normalize to a single ranked list the agent can print as context.
    """
    await _ensure_infra()

    # Kick off both searches
    vec_task = hybrid_search_tool(HybridSearchInput(query=query, limit=top_k, text_weight=0.3))
    kg_task = graph_search_tool(GraphSearchInput(query=query))
    vec_results, kg_results = await asyncio.gather(vec_task, kg_task, return_exceptions=False)

    # Normalize vector results
    unified: List[Dict[str, Any]] = []
    for r in vec_results or []:
        unified.append({
            "type": "vector",
            "text": r.content,
            "score": max(0.0, min(1.0, float(r.score))),
            "document_title": r.document_title,
            "document_source": r.document_source,
            "chunk_id": r.chunk_id
        })

    # Normalize graph results (no numeric score provided; give them a reasonable prior)
    # You can tweak this constant if you want KG facts to rank higher/lower.
    KG_PRIOR = 0.65
    for g in kg_results or []:
        unified.append({
            "type": "graph",
            "text": g.fact,
            "score": KG_PRIOR,
            "document_title": "",           # facts may not have a doc title
            "document_source": "knowledge_graph",
            "uuid": g.uuid,
            "valid_at": g.valid_at,
            "invalid_at": g.invalid_at
        })

    # Sort & cap
    unified.sort(key=lambda x: x["score"], reverse=True)
    return unified[:top_k]
