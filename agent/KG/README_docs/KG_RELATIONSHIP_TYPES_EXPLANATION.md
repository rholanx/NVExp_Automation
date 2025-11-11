# Knowledge Graph Relationship Types Explanation

## Overview

This document explains why you only see "MENTIONS" and "RELATES_TO" relationships in Neo4j, and how to add more relationship types to your knowledge graph.

---

## Current Relationship Types

### What You See in Neo4j

When examining your Neo4j knowledge graph, you see only two relationship types:
1. **`MENTIONS`**: Connects Episodic nodes (episodes) to Entity nodes
2. **`RELATES_TO`**: Connects Entity nodes to other Entity nodes

### Why Only These Two?

**Location**: Graphiti's core library (`graphiti_core/models/edges/edge_db_queries.py`)

These relationship types are **hardcoded in Graphiti's core library**:

```python
# Episode to Entity relationship
MERGE (episode)-[r:MENTIONS {uuid: $uuid}]->(node)

# Entity to Entity relationship  
MERGE (source)-[r:RELATES_TO {uuid: $uuid}]->(target)
```

**Key Point**: Graphiti uses a **two-tier relationship system**:
- **Neo4j Relationship Type**: Always `MENTIONS` or `RELATES_TO` (fixed)
- **Semantic Relationship Type**: Extracted by LLM (e.g., "FOUNDED", "WORKS_AT", "USES", "CONFIGURED") and stored as **properties** on the relationship

---

## How Graphiti Extracts Relationships

### LLM Extraction Process

**Location**: `graphiti_core/prompts/extract_edges.py`, lines 60-126

When Graphiti processes an episode, it:

1. **Extracts Entities**: First identifies all entities in the text
2. **Extracts Relationships**: Then uses an LLM to extract relationships between entities
3. **Relationship Type Format**: The LLM is instructed to use `SCREAMING_SNAKE_CASE` for relationship types:
   ```
   Use a SCREAMING_SNAKE_CASE string as the `relation_type` (e.g., FOUNDED, WORKS_AT).
   ```

### Example Extraction

**Input Text**:
```
"User: I need to run an ESR experiment with frequency range 2.8-3.0 GHz.
Assistant: I'll configure the ESR experiment with the specified frequency range."
```

**LLM Extracts**:
- Entity: "ESR experiment"
- Entity: "Frequency"
- Relationship: `USES` (ESR experiment → Frequency)
- Relationship: `CONFIGURED_WITH` (Assistant → ESR experiment)

### Storage in Neo4j

**What Gets Stored**:
```cypher
// Episode to Entity
(episode:Episodic)-[:MENTIONS]->(entity:Entity)

// Entity to Entity (with semantic type as property)
(entity1:Entity)-[:RELATES_TO {
    relation_type: "USES",
    fact_text: "ESR experiment uses frequency range 2.8-3.0 GHz",
    valid_at: "2025-01-08T11:31:20Z"
}]->(entity2:Entity)
```

**Important**: The semantic relationship type (e.g., "USES", "CONFIGURED_WITH") is stored as a **property** (`relation_type`) on the `RELATES_TO` relationship, **not** as a separate Neo4j relationship type.

---

## About scheme.sql

**Location**: `/export/jyuan98/quantum-sensing-agent/agent/KG/scheme.sql`

**Important**: The `scheme.sql` file is for **PostgreSQL** (the vector database), **NOT** for Neo4j!

- **PostgreSQL**: Uses SQL schema files (like `scheme.sql`) to define tables, indexes, and functions
- **Neo4j**: Is schema-less and doesn't use SQL schema files

**What `scheme.sql` Contains**:
- PostgreSQL table definitions (`documents`, `chunks`, `sessions`, `messages`)
- Vector search functions (`match_chunks`, `hybrid_search`)
- Indexes for performance

**What `scheme.sql` Does NOT Control**:
- ❌ Neo4j relationship types
- ❌ Graph structure in Neo4j
- ❌ Entity or relationship extraction

---

## How to Add More Relationship Types

### Option 1: Query by Semantic Relationship Type (Recommended)

**You don't need to change the Neo4j relationship types!** Instead, query by the `relation_type` property:

```cypher
// Find all relationships of type "USES"
MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
WHERE r.relation_type = "USES"
RETURN a, r, b

// Find all relationships of type "CONFIGURED_WITH"
MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
WHERE r.relation_type = "CONFIGURED_WITH"
RETURN a, r, b

// Find all unique relationship types
MATCH ()-[r:RELATES_TO]->()
RETURN DISTINCT r.relation_type AS relationship_type
```

**In Neo4j Browser**:
1. Run: `MATCH ()-[r:RELATES_TO]->() RETURN DISTINCT r.relation_type`
2. This shows all semantic relationship types that have been extracted

### Option 2: Customize Graphiti's LLM Prompts

**Location**: You would need to modify Graphiti's prompts (in the installed package)

**Not Recommended**: This requires modifying the Graphiti library code, which:
- Gets overwritten on updates
- Is complex and error-prone
- May break functionality

### Option 3: Create Custom Relationship Types in Neo4j (Advanced)

If you want **actual Neo4j relationship types** (not just properties), you can:

1. **Extract existing relationships and recreate them**:
```cypher
// Create custom relationship types from existing RELATES_TO relationships
MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
WHERE r.relation_type = "USES"
CREATE (a)-[r2:USES {
    uuid: r.uuid,
    fact_text: r.fact_text,
    valid_at: r.valid_at
}]->(b)
```

2. **Use Cypher to create relationships during ingestion**:
   - Modify the ingestion pipeline to create custom relationships
   - This requires custom code beyond Graphiti's default behavior

**Note**: This approach creates duplicate relationships and may cause confusion.

---

## Understanding the Current Structure

### Relationship Hierarchy

```
Episode (Episodic Node)
  └─[:MENTIONS]─→ Entity
                    └─[:RELATES_TO {relation_type: "USES"}]─→ Entity
                    └─[:RELATES_TO {relation_type: "CONFIGURED_WITH"}]─→ Entity
                    └─[:RELATES_TO {relation_type: "AFFECTS"}]─→ Entity
```

### Why This Design?

Graphiti uses this design because:
1. **Flexibility**: Can extract any relationship type without modifying Neo4j schema
2. **Simplicity**: Only two relationship types to manage in Neo4j
3. **Queryability**: Can still query by semantic type using properties
4. **LLM-Driven**: Relationship types are discovered by the LLM, not predefined

---

## Viewing Relationship Types in Neo4j

### Method 1: Query All Relationship Types

```cypher
// Get all unique semantic relationship types
MATCH ()-[r:RELATES_TO]->()
RETURN DISTINCT r.relation_type AS relationship_type, 
       count(*) AS count
ORDER BY count DESC
```

### Method 2: Visualize in Neo4j Browser

1. **Show all relationships**:
```cypher
MATCH (a)-[r:RELATES_TO]->(b)
RETURN a, r, b
LIMIT 50
```

2. **Click on a relationship** to see its properties, including `relation_type`

3. **Filter by relationship type**:
```cypher
MATCH (a)-[r:RELATES_TO]->(b)
WHERE r.relation_type = "USES"
RETURN a, r, b
```

### Method 3: Check Relationship Properties

```cypher
// See all properties on RELATES_TO relationships
MATCH ()-[r:RELATES_TO]->()
RETURN r LIMIT 1
```

This shows properties like:
- `relation_type`: The semantic relationship type (e.g., "USES", "CONFIGURED_WITH")
- `fact_text`: The original text describing the relationship
- `uuid`: Unique identifier
- `valid_at`: When the relationship became valid
- `invalid_at`: When the relationship became invalid (if applicable)

---

## Customizing Relationship Extraction

### Option 1: Guide LLM with Custom Prompts (Future Enhancement)

Currently, Graphiti doesn't expose a way to customize relationship extraction prompts in your code. However, you could:

1. **Modify Graphiti's initialization** to include custom prompts (requires library modification)
2. **Use Graphiti's `edge_types` parameter** (if available in future versions)

### Option 2: Post-Process Relationships

After ingestion, you can:

1. **Query relationships**:
```cypher
MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
WHERE r.relation_type IS NULL OR r.relation_type = ""
RETURN a, r, b
```

2. **Create new relationships** based on your own logic:
```cypher
// Example: Create a "CONFIGURED" relationship from existing data
MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
WHERE r.fact_text CONTAINS "configured"
CREATE (a)-[:CONFIGURED {
    uuid: r.uuid,
    fact_text: r.fact_text,
    valid_at: r.valid_at
}]->(b)
```

---

## Practical Examples

### Example 1: Find All Relationship Types in Your Graph

```cypher
// Get all unique semantic relationship types with counts
MATCH ()-[r:RELATES_TO]->()
WHERE r.relation_type IS NOT NULL
RETURN DISTINCT r.relation_type AS relationship_type, 
       count(*) AS count
ORDER BY count DESC
```

### Example 2: Find Relationships of a Specific Type

```cypher
// Find all "USES" relationships
MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
WHERE r.relation_type = "USES"
RETURN a.name AS from_entity, 
       b.name AS to_entity, 
       r.fact_text AS fact
LIMIT 20
```

### Example 3: Find Entities Connected by Specific Relationship Type

```cypher
// Find all entities that "CONFIGURED" something
MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
WHERE r.relation_type = "CONFIGURED" OR r.relation_type = "CONFIGURED_WITH"
RETURN a.name AS configurer, 
       b.name AS configured_item,
       r.fact_text AS fact
```

### Example 4: Visualize Relationships by Type

```cypher
// Visualize all relationships, colored by type
MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
WHERE r.relation_type IN ["USES", "CONFIGURED_WITH", "AFFECTS"]
RETURN a, r, b
```

**In Neo4j Browser**: This will show relationships with different colors/styles based on the `relation_type` property.

---

## Summary

### Why Only "MENTIONS" and "RELATES_TO"?

- ✅ **By Design**: Graphiti uses a two-tier system with fixed Neo4j relationship types
- ✅ **Semantic Types as Properties**: Actual relationship types (e.g., "USES", "CONFIGURED_WITH") are stored as properties
- ✅ **LLM-Driven**: Relationship types are extracted by the LLM, not predefined

### Where to Change?

- ❌ **NOT in `scheme.sql`**: This file is for PostgreSQL, not Neo4j
- ✅ **Query by Properties**: Use Cypher to query by `relation_type` property
- ⚠️ **Graphiti Library**: Relationship types are hardcoded in the library (not easily changeable)

### Recommended Approach

1. **Query by semantic type**: Use `WHERE r.relation_type = "YOUR_TYPE"` in Cypher queries
2. **View all types**: Run `MATCH ()-[r:RELATES_TO]->() RETURN DISTINCT r.relation_type`
3. **Accept the design**: The two-tier system is flexible and works well for most use cases

### Key Takeaway

The relationship types you see in Neo4j (`MENTIONS`, `RELATES_TO`) are **structural**, while the actual relationship types (e.g., "USES", "CONFIGURED_WITH") are **semantic** and stored as properties. This design allows Graphiti to extract any relationship type without modifying the Neo4j schema.

### Next Steps

1. **Run the query** in Example 1 to see what relationship types Graphiti has extracted from your data
2. **Use property-based queries** to filter by semantic relationship types
3. **Consider the design**: The two-tier system is actually quite flexible and doesn't require changes

---

## How Relationship Properties Affect Search and Returned Facts

### Overview

The relationship properties (especially `fact_embedding`, `fact_text`, and `relation_type`) **significantly impact** both the search process and which facts are returned. Understanding this helps explain why certain facts appear in search results.

---

### 1. Impact on Search Process

#### A. Primary Search Mechanism: `fact_embedding`

**Location**: Graphiti's search uses vector similarity on `fact_embedding`

**How It Works**:
1. **Query Embedding**: Your search query is converted to an embedding vector
2. **Fact Embedding Comparison**: Graphiti compares this query embedding against the `fact_embedding` property on all `RELATES_TO` relationships
3. **Similarity Scoring**: Relationships with similar embeddings are ranked higher
4. **Result Selection**: Top-scoring relationships (facts) are returned

**Key Point**: The `fact_embedding` property is the **primary mechanism** for finding relevant facts. It's created when the relationship is first extracted from text.

**Example**:
```
Query: "ESR experiment configuration"
  ↓ (converted to embedding)
Compare against fact_embedding on all RELATES_TO relationships
  ↓
Find: fact_embedding similar to query embedding
  ↓
Return: Facts with high similarity scores
```

#### B. Secondary Mechanism: `fact_text` (Semantic Content)

**Location**: The `fact` property contains the actual text of the relationship

**How It Works**:
1. The `fact_text` is what gets embedded to create `fact_embedding`
2. The semantic meaning in `fact_text` determines the embedding
3. Search finds facts where the semantic meaning matches the query

**Example**:
```
fact_text: "ESR experiment uses frequency range 2.8-3.0 GHz"
  ↓ (embedded)
fact_embedding: [0.123, -0.456, 0.789, ...] (1536 dimensions)
  ↓ (compared with query embedding)
Similarity score: 0.87 (high match)
  ↓
Returned in search results
```

#### C. Relationship Type (`relation_type`): Currently NOT Used in Search

**Important**: The `relation_type` property (e.g., "USES", "CONFIGURED_WITH") is **stored but not directly used** in Graphiti's default search algorithm.

**What This Means**:
- ❌ Searching for "USES" won't filter to only "USES" relationships
- ✅ Search is based on semantic similarity, not relationship type labels
- ✅ All relationship types are searched equally

**Why**: Graphiti prioritizes semantic meaning over relationship type labels. A query about "configuration" will find facts with `relation_type` of "CONFIGURED", "SETS_UP", "INITIALIZES", etc., if they're semantically similar.

---

### 2. Impact on Returned Facts

#### A. Which Facts Are Returned

**Determined By**:
1. **Semantic Similarity**: Facts with `fact_embedding` similar to query embedding
2. **Graph Traversal**: Facts connected to entities found in the query
3. **Context**: Facts from the same episodes or related entities

**NOT Determined By**:
- ❌ `relation_type` property (not used for filtering)
- ❌ Relationship type labels (semantic search ignores these)

#### B. Example: How Properties Affect Results

**Scenario**: Query "ESR frequency configuration"

**Graph Structure**:
```
Entity: "ESR experiment"
  └─[:RELATES_TO {
      relation_type: "USES",
      fact: "ESR experiment uses frequency range 2.8-3.0 GHz",
      fact_embedding: [0.123, -0.456, ...]
    }]─→ Entity: "Frequency"

Entity: "Assistant"
  └─[:RELATES_TO {
      relation_type: "CONFIGURED",
      fact: "Assistant configured ESR experiment with frequency settings",
      fact_embedding: [0.234, -0.567, ...]
    }]─→ Entity: "ESR experiment"
```

**Search Process**:
1. Query "ESR frequency configuration" → embedding: `[0.145, -0.489, ...]`
2. Compare with all `fact_embedding` values
3. Both facts have high similarity (both mention ESR + frequency + configuration)
4. **Both facts are returned**, regardless of their `relation_type`

**Result**:
- ✅ Fact 1: "ESR experiment uses frequency range 2.8-3.0 GHz" (relation_type: "USES")
- ✅ Fact 2: "Assistant configured ESR experiment with frequency settings" (relation_type: "CONFIGURED")

**Key Insight**: The `relation_type` doesn't determine which facts are returned—**semantic similarity does**.

---

### 3. Temporal Properties: `valid_at` and `invalid_at`

#### Impact on Search

**Location**: These properties can be used for temporal filtering (if implemented)

**How They Work**:
- `valid_at`: When the fact became valid/true
- `invalid_at`: When the fact became invalid/false (if applicable)

**Current Implementation**:
- ⚠️ Graphiti's default search doesn't filter by these properties
- ✅ They're stored and can be queried manually
- ✅ Can be used for temporal reasoning in custom queries

**Example Use Case**:
```cypher
// Find facts valid at a specific time
MATCH ()-[r:RELATES_TO]->()
WHERE r.valid_at <= "2025-01-08T12:00:00Z"
  AND (r.invalid_at IS NULL OR r.invalid_at > "2025-01-08T12:00:00Z")
RETURN r.fact
```

---

### 4. Practical Implications

#### A. Why Some Facts Appear in Results

**Facts appear because**:
1. ✅ Their `fact_embedding` is similar to the query embedding
2. ✅ They're connected to entities mentioned in the query
3. ✅ They share context with other relevant facts

**Facts DON'T appear because**:
- ❌ They have a specific `relation_type`
- ❌ They match a relationship type label

#### B. How to Filter by Relationship Type (Manual)

If you want to filter results by `relation_type`, you need to do it **after** Graphiti's search:

```python
# In your code, after getting search results
results = await graph_client.search(query)

# Filter by relationship type
filtered_results = [
    r for r in results 
    if r.get('relation_type') == 'USES'  # If relation_type is available
]
```

**Note**: The current implementation doesn't expose `relation_type` in search results. You'd need to query Neo4j directly to filter by relationship type.

#### C. Custom Search with Relationship Type Filtering

To search with relationship type filtering, you could:

1. **Query Neo4j directly**:
```cypher
// Search with relationship type filter
MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
WHERE r.relation_type = "USES"
  AND r.fact CONTAINS "ESR"
RETURN r.fact AS fact
```

2. **Modify search implementation** to include relationship type in results and filter

---

### 5. Summary: Property Impact

#### Properties That Affect Search:

| Property | Impact on Search | Impact on Results |
|----------|-----------------|-------------------|
| `fact_embedding` | ✅ **PRIMARY** - Used for vector similarity | ✅ Determines which facts are returned |
| `fact` / `fact_text` | ✅ **SECONDARY** - Source of embedding | ✅ The actual text returned to user |
| `relation_type` | ❌ **NOT USED** - Stored but ignored | ❌ Doesn't affect which facts are returned |
| `valid_at` | ⚠️ **POTENTIAL** - Can be used for filtering | ⚠️ Could filter by time (not currently used) |
| `invalid_at` | ⚠️ **POTENTIAL** - Can be used for filtering | ⚠️ Could filter by time (not currently used) |

#### Key Takeaways:

1. **Semantic Search Dominates**: Search is based on meaning (`fact_embedding`), not labels (`relation_type`)
2. **Relationship Types Are Metadata**: `relation_type` is stored for reference but doesn't affect search
3. **Graph Structure Matters**: Facts connected to relevant entities are more likely to be found
4. **Temporal Properties Available**: Can be used for custom temporal queries, but not in default search

#### Why This Design?

- **Flexibility**: Semantic search finds relevant facts regardless of how they're labeled
- **LLM-Driven**: Relationship types are extracted by LLM, which may vary in naming
- **Focus on Meaning**: Prioritizes semantic similarity over rigid categorization

---

### 6. Practical Recommendations

#### For Better Search Results:

1. **Focus on Content**: The `fact_text` content determines search results, so ensure it's descriptive
2. **Don't Rely on Types**: Don't expect filtering by `relation_type` to work in default search
3. **Use Graph Traversal**: Facts connected to relevant entities will be found through graph structure

#### For Relationship Type Filtering:

1. **Query Neo4j Directly**: Use Cypher queries to filter by `relation_type` after ingestion
2. **Custom Search Function**: Create a custom search that includes relationship type filtering
3. **Post-Process Results**: Filter Graphiti's results by querying Neo4j for relationship types

#### For Temporal Filtering:

1. **Custom Queries**: Use `valid_at` and `invalid_at` in custom Cypher queries
2. **Time-Based Search**: Implement time-range filtering in your search logic
3. **Temporal Reasoning**: Use these properties for "what was true at time X" queries

---

## Multi-Hop Reasoning Example: A causes B, B+C causes D

### Your Scenario

**Stored Facts**:
- Fact 1: "A causes B"
- Fact 2: "B together with C causes D"

**Query**: "D"

**Question**: What facts would appear in the search results?

---

### What Would Appear

#### 1. **Direct Fact About D** (High Priority)

**Fact**: "B together with C causes D"

**Why It Appears**:
- ✅ **Direct Match**: The fact directly mentions "D"
- ✅ **High Semantic Similarity**: Query "D" has high embedding similarity with fact containing "D"
- ✅ **Top Result**: This would likely be the **highest-ranked result**

**Graph Structure**:
```
Entity: "B" ──[:RELATES_TO {fact: "B together with C causes D"}]──> Entity: "D"
Entity: "C" ──[:RELATES_TO {fact: "B together with C causes D"}]──> Entity: "D"
```

---

#### 2. **Indirect Fact Through Graph Traversal** (Medium Priority)

**Fact**: "A causes B"

**Why It Appears**:
- ✅ **Graph Traversal**: Graphiti uses BFS (Breadth-First Search) to traverse relationships
- ✅ **Multi-Hop Path**: D → B → A (2 hops)
- ✅ **Connected Context**: Since B is connected to D, facts about B are discovered
- ⚠️ **Lower Priority**: May appear with lower score than direct facts

**Graph Traversal Path**:
```
Query: "D"
  ↓ (find Entity D)
Entity: "D"
  ↓ (traverse relationships)
Entity: "B" (connected to D via "B together with C causes D")
  ↓ (traverse relationships from B)
Entity: "A" (connected to B via "A causes B")
  ↓
Return: Fact "A causes B"
```

**Graph Structure**:
```
Entity: "A" ──[:RELATES_TO {fact: "A causes B"}]──> Entity: "B"
  └─ (connected through)
Entity: "B" ──[:RELATES_TO {fact: "B together with C causes D"}]──> Entity: "D"
```

---

### Search Process Breakdown

#### Step 1: Semantic Search for "D"

1. **Query Embedding**: Convert "D" to embedding vector
2. **Vector Similarity**: Compare against all `fact_embedding` values
3. **Direct Matches**: Find facts with high similarity (containing "D")
   - ✅ "B together with C causes D" (high score)

#### Step 2: Graph Traversal (BFS)

**Location**: Graphiti's `edge_bfs_search` function

**Process**:
1. **Find Center Nodes**: Entities matching "D" (Entity D)
2. **BFS Traversal**: Starting from Entity D, traverse relationships
   ```
   MATCH path = (origin:Entity {uuid: D_uuid})-[:RELATES_TO|MENTIONS]->{1,3}(n:Entity)
   ```
3. **Discover Connected Facts**: Find facts connected to entities in the path
   - Entity D → Entity B (via "B together with C causes D")
   - Entity B → Entity A (via "A causes B")
4. **Return Connected Facts**: "A causes B" is discovered through the path

#### Step 3: Result Ranking

**Ranking Order** (likely):
1. **"B together with C causes D"** (highest score)
   - Direct mention of "D"
   - High semantic similarity
   
2. **"A causes B"** (lower score)
   - Indirect connection through graph traversal
   - Lower semantic similarity to query "D"
   - But still relevant because B is connected to D

---

### Expected Search Results

**Query**: "D"

**Results** (in order of relevance):

1. ✅ **"B together with C causes D"**
   - **Type**: Direct match
   - **Score**: High (0.85-0.95)
   - **Reason**: Directly mentions D, high semantic similarity

2. ✅ **"A causes B"** (if graph traversal is enabled)
   - **Type**: Indirect match (2-hop)
   - **Score**: Medium (0.60-0.75)
   - **Reason**: Connected through graph: D → B → A
   - **Path**: Entity D is connected to Entity B, Entity B is connected to Entity A

---

### Factors That Affect Results

#### A. Graph Traversal Depth

**Location**: `KG/graph_utils.py`, line 166
```python
center_node_distance: int = 2  # Default: 2 hops
```

**Impact**:
- **Distance = 1**: Only direct connections (D → B), might not find "A causes B"
- **Distance = 2**: 2-hop traversal (D → B → A), **will find "A causes B"**
- **Distance = 3**: 3-hop traversal, finds even more distant facts

**Note**: The current implementation doesn't use this parameter, but Graphiti internally uses BFS with depth 1-3.

#### B. Semantic Similarity Threshold

**Location**: Graphiti's search uses a minimum similarity score

**Impact**:
- If "A causes B" has low semantic similarity to query "D", it might not appear
- Graph traversal helps, but semantic similarity still matters

#### C. Graph Structure Quality

**Impact**:
- If entities A, B, C, D are properly extracted and connected, traversal works well
- If entities are not properly linked, traversal may miss connections

---

### Visual Example

**Graph Structure in Neo4j**:
```
Entity: "A"
  └─[:RELATES_TO {
      fact: "A causes B",
      fact_embedding: [...],
      relation_type: "CAUSES"
    }]─→ Entity: "B"
          └─[:RELATES_TO {
              fact: "B together with C causes D",
              fact_embedding: [...],
              relation_type: "CAUSES"
            }]─→ Entity: "D"
          └─[:RELATES_TO {
              fact: "B together with C causes D",
              fact_embedding: [...],
              relation_type: "CAUSES"
            }]─→ Entity: "C"
```

**Query**: "D"

**Search Process**:
1. **Semantic Search**: Find facts with "D" → "B together with C causes D"
2. **Graph Traversal from Entity D**:
   - Find Entity D
   - Traverse to Entity B (via "B together with C causes D")
   - Traverse to Entity A (via "A causes B")
   - Return fact: "A causes B"

---

### Key Insights

1. **Direct Facts Always Appear**: Facts directly mentioning the query entity will have highest priority

2. **Graph Traversal Enables Multi-Hop Reasoning**: 
   - Can discover facts 2-3 hops away
   - Enables causal chain reasoning: D → B → A

3. **Semantic Similarity Still Matters**: 
   - Even with graph traversal, facts need some semantic relevance
   - "A causes B" might not appear if it's semantically unrelated to "D"

4. **Both Mechanisms Work Together**:
   - Semantic search finds direct matches
   - Graph traversal finds connected facts
   - Combined, they provide comprehensive results

---

### Practical Implications

#### For Your Use Case:

**If you query "D"**, you would get:
- ✅ **Direct fact**: "B together with C causes D" (definitely appears)
- ✅ **Indirect fact**: "A causes B" (likely appears through graph traversal)

**This enables causal reasoning**:
- You can infer: "If A causes B, and B+C causes D, then A indirectly relates to D"
- The graph structure makes this connection discoverable

#### To Ensure Multi-Hop Facts Appear:

1. **Ensure Proper Entity Extraction**: A, B, C, D must be properly extracted as entities
2. **Ensure Proper Relationships**: Facts must create proper `RELATES_TO` relationships
3. **Graph Traversal Enabled**: Graphiti's BFS search must be active (it is by default)

---

### Summary

**Query**: "D"

**What Pops Up**:

1. ✅ **"B together with C causes D"** 
   - **Why**: Direct mention, high semantic similarity
   - **Priority**: Highest

2. ✅ **"A causes B"** 
   - **Why**: Graph traversal (D → B → A), 2-hop connection
   - **Priority**: Medium (if graph traversal finds it)

**Key Point**: The graph structure enables **multi-hop causal reasoning**, allowing you to discover that A is indirectly related to D through the chain A → B → D.

