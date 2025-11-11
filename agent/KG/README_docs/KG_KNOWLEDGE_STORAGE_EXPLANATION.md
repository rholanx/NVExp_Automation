# Knowledge Graph Storage and Retrieval Explanation

## Overview

This document explains how knowledge graph information is stored and why retrieved knowledge appears as sentences. The knowledge graph uses **Graphiti** (built on Neo4j) to store and retrieve structured facts extracted from documents and conversations.

---

## How Knowledge Graph Information is Stored

### 1. **Storage Process Flow**

The storage process follows these steps:

#### Step 1: Content Chunking
- **Location**: `KG_rag_engine.py`, lines 181-183, 314-316
- Documents or conversations are split into chunks using a chunker
- Each chunk contains text content (typically 1000-2000 characters)

#### Step 2: Episode Creation
- **Location**: `KG/ingestion/graph_builder.py`, lines 118-130
- Each chunk is converted into an "episode" in the knowledge graph
- An episode contains:
  - `episode_id`: Unique identifier
  - `episode_body`: The chunk content (text)
  - `source_description`: Document title and chunk index
  - `reference_time`: Timestamp when the episode was added
  - `metadata`: Additional information (document title, source, chunk index)

#### Step 3: Graphiti Processing
- **Location**: `KG/graph_utils.py`, lines 153-159
- Graphiti (the knowledge graph framework) processes each episode:
  - Uses an LLM to extract structured facts from the episode content
  - Creates nodes (entities) and relationships in Neo4j
  - Stores facts as structured knowledge statements
  - Each fact is stored as a **sentence** that represents a piece of knowledge

**Key Point**: Graphiti automatically extracts facts from the episode content and stores them as **natural language sentences** that represent structured knowledge.

---

## How Knowledge Graph Information is Retrieved

### 1. **Retrieval Process Flow**

#### Step 1: Search Query
- **Location**: `KG_rag_engine.py`, line 133
- A user query is passed to `perform_comprehensive_search()`

#### Step 2: Graph Search Execution
- **Location**: `KG/tools.py`, lines 143-172
- The `graph_search_tool()` function:
  - Calls `search_knowledge_graph(query)` from `graph_utils.py`
  - Graphiti performs semantic search on the stored facts
  - Returns `GraphSearchResult` objects

#### Step 3: Fact Extraction
- **Location**: `KG/graph_utils.py`, lines 185-197
- Graphiti's `search()` method returns results where each result has:
  - `result.fact`: **A sentence string** containing the extracted knowledge
  - `result.uuid`: Unique identifier for the fact
  - `result.valid_at`: When the fact became valid (optional)
  - `result.invalid_at`: When the fact became invalid (optional)
  - `result.source_node_uuid`: Reference to the source episode

#### Step 4: Result Formatting
- **Location**: `KG_rag_engine.py`, lines 149-157
- The graph results are formatted into the agent's expected format:
  ```python
  {
      "type": "graph",
      "text": g.fact,  # <-- This is the sentence!
      "score": 1.0,
      "title": "Knowledge Graph Fact",
      "source": "knowledge_graph"
  }
  ```

**Key Point**: The `g.fact` field (line 153) contains a **sentence** because Graphiti stores and retrieves knowledge as natural language sentences representing structured facts.

---

## Why Facts are Sentences

### Graphiti's Design Philosophy

Graphiti is designed to store knowledge as **structured facts in natural language form**. When Graphiti processes an episode:

1. **Extraction**: It uses an LLM to extract meaningful facts from the episode content
2. **Normalization**: It converts these facts into clear, declarative sentences
3. **Storage**: It stores these sentences in Neo4j as fact nodes
4. **Retrieval**: When searching, it returns these stored sentences that match the query

### Example Flow

**Original Episode Content** (from a conversation chunk):
```
"User: I need to run an ESR experiment with frequency range 2.8-3.0 GHz.
Assistant: I'll configure the ESR experiment with the specified frequency range."
```

**Graphiti Extracts Facts** (stored as sentences):
- `"The user requested an ESR experiment with frequency range 2.8-3.0 GHz"`
- `"The assistant configured an ESR experiment with frequency range 2.8-3.0 GHz"`
- `"ESR experiments can be configured with specific frequency ranges"`

**When Retrieved** (via search):
- Query: "ESR frequency configuration"
- Returns: `"The assistant configured an ESR experiment with frequency range 2.8-3.0 GHz"`

---

## Data Structure Details

### GraphSearchResult Model
- **Location**: `KG/models.py`, lines 77-83
```python
class GraphSearchResult(BaseModel):
    fact: str              # The sentence containing the knowledge
    uuid: str             # Unique identifier
    valid_at: Optional[str]  # When fact became valid
    invalid_at: Optional[str]  # When fact became invalid
    source_node_uuid: Optional[str]  # Reference to source episode
```

### Storage in Neo4j
- **Graph Structure**: Nodes (entities, facts) and relationships (connections between entities)
- **Fact Nodes**: Store the sentence text as a property
- **Episode Nodes**: Store the original chunk content
- **Relationships**: Connect facts to episodes, entities to facts, etc.

---

## Key Code Locations

### Storage
1. **Episode Addition**: `KG/graph_utils.py`, lines 127-161 (`add_episode()`)
2. **Graph Building**: `KG/ingestion/graph_builder.py`, lines 63-154 (`add_document_to_graph()`)
3. **Episode Content Preparation**: `KG/ingestion/graph_builder.py`, lines 156-200 (`_prepare_episode_content()`)

### Retrieval
1. **Search Entry Point**: `KG_rag_engine.py`, line 133 (`perform_comprehensive_search()`)
2. **Graph Search Tool**: `KG/tools.py`, lines 143-172 (`graph_search_tool()`)
3. **Graph Search Implementation**: `KG/graph_utils.py`, lines 163-201 (`search()`)
4. **Result Formatting**: `KG_rag_engine.py`, lines 149-157 (graph results formatting)

### Where the Sentence Appears
- **Primary Location**: `KG_rag_engine.py`, line 153
  ```python
  "text": g.fact if hasattr(g, "fact") else g.get("fact", "")
  ```
  This line extracts the `fact` field (which is a sentence) from the `GraphSearchResult` object.

- **Source of Fact**: `KG/graph_utils.py`, line 190
  ```python
  "fact": result.fact,
  ```
  This comes from Graphiti's search result, where `result.fact` is a sentence string.

---

## How Graph Structure Affects Search and Retrieved Facts

### Overview

The graph structure (nodes, relationships, connections) **affects both the search process AND the facts that are returned**. It's not just about finding facts—the graph structure determines **which facts are discovered** and **how they're connected** to provide context.

---

### 1. Impact on Search Process

#### A. Semantic Search with Graph Context

**Location**: `KG/graph_utils.py`, line 185
```python
results = await self.graphiti.search(query)
```

Graphiti's search uses a **hybrid approach**:

1. **Semantic Similarity**: Uses embeddings to find facts semantically similar to the query
2. **Graph Traversal**: Leverages relationships to find related facts that might not directly match the query text
3. **Context Propagation**: Uses graph connections to understand context and relationships

**Example**:
- Query: "ESR experiment configuration"
- Direct match: Facts directly mentioning "ESR experiment configuration"
- Graph traversal: Facts connected to ESR-related entities (frequency, NV center, etc.)
- Context: Facts from the same episode or related episodes

#### B. Graph-Aware Search Parameters

**Location**: `KG/graph_utils.py`, lines 163-168
```python
async def search(
    self,
    query: str,
    center_node_distance: int = 2,  # <-- Graph structure parameter
    use_hybrid_search: bool = True
)
```

**Note**: While `center_node_distance` is defined, the current implementation (line 185) doesn't use it. However, Graphiti internally uses graph structure for search.

**How Graph Structure Affects Search**:

1. **Entity Relationships**: When searching for "ESR", Graphiti can:
   - Find facts directly about ESR
   - Traverse relationships to find related entities (frequency, NV center, configuration)
   - Discover facts connected through multiple hops

2. **Episode Connections**: Facts from the same episode are more likely to be retrieved together because they share graph connections

3. **Temporal Relationships**: Facts with temporal relationships (valid_at, invalid_at) can be filtered or prioritized based on time

---

### 2. Impact on Returned Facts

**The graph structure DIRECTLY affects which facts are returned**, not just how they're found.

#### A. Related Facts Through Graph Traversal

**Location**: `KG/graph_utils.py`, lines 203-245 (`get_related_entities()`)

When you search for an entity, Graphiti can return facts that are:
- **Directly connected** to the query entity
- **Indirectly connected** through relationships (2-3 hops away)
- **Contextually related** through shared episodes or entities

**Example Scenario**:

**Graph Structure**:
```
Episode: "ESR experiment conversation"
  ├─ Fact: "User requested ESR experiment with 2.8-3.0 GHz"
  ├─ Fact: "Assistant configured ESR experiment"
  └─ Entity: "ESR" ──[related_to]──> Entity: "Frequency"
                                      └─ Fact: "Frequency range affects NV center resonance"
```

**Query**: "ESR experiment"

**Without Graph Structure** (pure semantic search):
- Returns: Only facts directly mentioning "ESR experiment"

**With Graph Structure** (graph-aware search):
- Returns: 
  1. Facts directly about "ESR experiment"
  2. Facts about "Frequency" (connected entity)
  3. Facts about "NV center resonance" (connected through frequency)
  4. Facts from the same episode (shared context)

#### B. Multi-Hop Reasoning

The graph structure enables **multi-hop reasoning**—finding facts that require traversing multiple relationships.

**Example**:
- Query: "What frequency was used in the last ESR experiment?"
- Graph traversal:
  1. Find "ESR experiment" entity
  2. Traverse to "last experiment" relationship
  3. Traverse to "frequency" entity
  4. Return: "Frequency range 2.8-3.0 GHz was used"

**Without graph structure**: Would only return facts explicitly stating "frequency" and "ESR" together.

**With graph structure**: Can connect separate facts through relationships.

#### C. Contextual Relevance

**Location**: `KG/models.py`, line 83
```python
source_node_uuid: Optional[str]  # Reference to source episode
```

The graph structure maintains **source relationships**, which affects:

1. **Episode Grouping**: Facts from the same episode are more likely to be returned together
2. **Temporal Context**: Facts with temporal relationships can be filtered by time
3. **Source Tracking**: Can trace facts back to their original episodes

**Example**:
- Facts from the same conversation episode share graph connections
- When searching, Graphiti can return related facts from the same context
- This provides more coherent, contextually relevant results

---

### 3. Current Implementation vs. Full Graph Capabilities

#### What's Currently Used

**Location**: `KG/graph_utils.py`, line 185
```python
results = await self.graphiti.search(query)
```

The current implementation uses Graphiti's default search, which:
- ✅ Uses semantic similarity (embeddings)
- ✅ Leverages graph structure internally (Graphiti does this automatically)
- ✅ Returns facts connected through relationships
- ⚠️ Doesn't explicitly control graph traversal depth (uses Graphiti defaults)

#### What Could Be Enhanced

**Location**: `KG/graph_utils.py`, lines 163-168

The `search()` method has parameters that could be used:
- `center_node_distance`: Control how far to traverse from center nodes
- `use_hybrid_search`: Combine semantic and graph-based search

**Entity Relationship Queries**:

**Location**: `KG/graph_utils.py`, lines 203-245

There are specialized functions for graph traversal:
- `get_related_entities()`: Explicitly traverse relationships
- `get_entity_timeline()`: Use temporal relationships

These show that **graph structure is actively used** for specialized queries.

---

### 4. Concrete Examples

#### Example 1: Direct vs. Indirect Facts

**Graph Structure**:
```
Episode 1: "ESR Configuration"
  └─ Fact: "ESR experiment uses frequency 2.8 GHz"
      └─ Entity: "ESR" ──[uses]──> Entity: "Frequency"
                                    └─ Fact: "Frequency affects NV center resonance"

Episode 2: "NV Center Properties"
  └─ Fact: "NV center resonance occurs at specific frequencies"
      └─ Entity: "NV Center" ──[resonates_at]──> Entity: "Frequency"
```

**Query**: "ESR experiment"

**Without Graph Structure**:
- Returns: Only "ESR experiment uses frequency 2.8 GHz"

**With Graph Structure**:
- Returns:
  1. "ESR experiment uses frequency 2.8 GHz" (direct)
  2. "Frequency affects NV center resonance" (1-hop: ESR → Frequency)
  3. "NV center resonance occurs at specific frequencies" (2-hop: ESR → Frequency → NV Center)

**The graph structure changed which facts were returned!**

#### Example 2: Contextual Grouping

**Graph Structure**:
```
Episode: "Conversation about ESR"
  ├─ Fact: "User asked about ESR configuration"
  ├─ Fact: "Assistant suggested 2.8-3.0 GHz range"
  └─ Fact: "User approved the configuration"
```

**Query**: "ESR configuration"

**Without Graph Structure**:
- Might return facts from different episodes, losing context

**With Graph Structure**:
- Returns facts from the same episode together
- Maintains conversational context
- Provides complete picture of the interaction

---

### 5. Summary: Graph Structure Impact

#### On Search Process:
- ✅ **Enables graph traversal**: Finds facts through relationships, not just text similarity
- ✅ **Contextual search**: Uses episode and entity connections
- ✅ **Multi-hop reasoning**: Can traverse multiple relationships
- ✅ **Semantic + structural**: Combines embeddings with graph structure

#### On Returned Facts:
- ✅ **More comprehensive**: Returns related facts through graph connections
- ✅ **Contextually relevant**: Groups facts from same episodes/contexts
- ✅ **Indirect connections**: Discovers facts not directly matching query text
- ✅ **Temporal awareness**: Can filter/prioritize by time relationships

**Key Answer**: The graph structure **affects BOTH search AND returned facts**. It's not just about finding facts faster—it fundamentally changes **which facts are discovered and returned** by enabling relationship traversal, multi-hop reasoning, and contextual grouping.

---

## Summary

1. **Storage**: Content is stored as episodes → Graphiti extracts facts as sentences → Stored in Neo4j
2. **Retrieval**: Query → Graphiti semantic search → Returns fact sentences → Formatted for agent
3. **Why Sentences**: Graphiti's design stores knowledge as natural language sentences representing structured facts
4. **Key Location**: The sentence appears in `KG_rag_engine.py` line 153 as `g.fact`, which comes from Graphiti's `GraphSearchResult.fact` field
5. **Graph Structure Impact**: 
   - **Search**: Enables graph traversal, multi-hop reasoning, contextual search
   - **Returned Facts**: Determines which facts are discovered through relationships, not just text matching

The retrieved knowledge is a sentence because **Graphiti stores and retrieves knowledge as natural language sentences** that represent structured facts extracted from the original content. The graph structure **fundamentally changes which facts are returned** by enabling relationship-based discovery beyond simple text matching.


