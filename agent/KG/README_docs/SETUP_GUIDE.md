# Knowledge Graph and Vector Database Setup Guide

This guide walks you through setting up the Knowledge Graph (KG) and Vector Database infrastructure required for the quantum-sensing-agent system.

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Database Configuration](#2-database-configuration)
3. [Document Preparation](#3-document-preparation)
4. [Ingestion Process](#4-ingestion-process)
5. [Running the Agent](#5-running-the-agent)

---

## 1. Environment Setup

### Install Required Packages

First, install all required Python packages from the `kg_requirements.txt` file:

```bash
pip install -r kg_requirements.txt
```
---

## 2. Database Configuration

### 2.1 Set Up PostgreSQL/Neon Database

1. **Create a Neon Database** (or use an existing PostgreSQL instance with pgvector extension)

2. **Copy the Database Schema**

   You need to execute the `scheme.sql` file in your Neon database. The schema file is located at:
   ```
   agent/KG/scheme.sql
   ```

   **Steps to apply the schema:**
   - Log into your Neon dashboard
   - Navigate to the SQL Editor
   - Copy the entire contents of `scheme.sql`
   - Paste and execute it in the SQL Editor
   
   **Alternatively, using command line:**
   ```bash
   psql <your-neon-connection-string> < agent/KG/scheme.sql
   ```

   The schema creates:
   - `documents` table for storing document metadata
   - `chunks` table with vector embeddings (using pgvector)
   - `sessions` and `messages` tables for conversation tracking
   - Vector search functions (`match_chunks`, `hybrid_search`)
   - Required indexes for efficient querying

### 2.2 Set Up Neo4j Graph Database

1. **Install Neo4j** (if not already installed)
   - Option 1: Use Neo4j Desktop
   - Option 2: Use Neo4j Aura (cloud service)
   - Option 3: Use Docker: `docker run -p 7474:7474 -p 7687:7687 neo4j:latest`

2. **Note your Neo4j connection details:**
   - URI (default: `bolt://localhost:7687`)
   - Username (default: `neo4j`)
   - Password (set during installation)

---

## 3. Document Preparation

### Add Documents to the Documents Directory

1. **Locate the documents directory:**
   ```
   agent/KG/documents/
   ```

2. **Add your documents:**
   - Place markdown files (`.md`, `.markdown`)
   - Text files (`.txt`)
   - Log files (`.log`)
   - The ingestion script will recursively search for these file types

3. **Document Format:**
   - Documents can include YAML frontmatter for metadata
   - Markdown headers (`# Title`) will be used as document titles
   - If no title is found, the filename will be used

**Example document structure:**
```
agent/KG/documents/
├── agent_history_20250408_150021.log
├── agent_history_20250416_180902.log
├── documentation.md
└── notes.txt
```

---

## 4. Ingestion Process

### 4.1 Configure Environment Variables

Create a `.env` file in the project root directory with the following required variables:

```bash
# PostgreSQL/Neon Database
DATABASE_URL=postgresql://user:password@host:port/database

# Neo4j Graph Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# LLM Configuration (for graph building and entity extraction)
LLM_API_KEY=your_openai_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_CHOICE=gpt-4-turbo-preview

# Embedding Configuration
EMBEDDING_API_KEY=your_openai_api_key
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small

# Optional: Vector dimensions (default: 1536)
VECTOR_DIMENSION=1536
```

**Important:** 
- Replace all placeholder values with your actual credentials
- Keep your `.env` file secure and never commit it to version control
- The `DATABASE_URL` should point to your Neon database with the schema already applied

### 4.2 Run the Ingestion Script

Navigate to the project root directory and run:

```bash
python agent/KG/ingestion/ingest.py
```

**Common options:**

```bash
# Basic ingestion
python agent/KG/ingestion/ingest.py

# Clean existing data before ingestion
python agent/KG/ingestion/ingest.py --clean

# Specify custom documents directory
python agent/KG/ingestion/ingest.py --documents ./path/to/documents

# Adjust chunking parameters
python agent/KG/ingestion/ingest.py --chunk-size 1000 --chunk-overlap 200

# Fast mode (skip knowledge graph building)
python agent/KG/ingestion/ingest.py --fast

# Graph-only mode (update KG only, skip PostgreSQL)
python agent/KG/ingestion/ingest.py --graph-only

# Verbose logging
python agent/KG/ingestion/ingest.py --verbose
```

**What the ingestion process does:**

1. **Chunking**: Splits documents into smaller chunks with configurable size and overlap
2. **Embedding**: Generates vector embeddings for each chunk using the configured embedding model
3. **PostgreSQL Storage**: Saves documents and chunks with embeddings to the vector database
4. **Entity Extraction**: Extracts entities (companies, technologies, people) from chunks
5. **Graph Building**: Creates knowledge graph relationships in Neo4j based on document content

**Expected output:**
```
INGESTION SUMMARY
==================================================
Documents processed: X
Total chunks created: Y
Total entities extracted: Z
Total graph episodes: W
Total processing time: T seconds
```

---

## 5. Running the Agent

Once the database and knowledge graph are set up, you can start using the agent:

### 5.1 Basic Usage

```bash
# Using embeddings mode (local embeddings directory)
python agent/agent.py

# Using Knowledge Graph mode (vector search only)
python agent/agent.py --use_KG

# Using Knowledge Graph mode with both vector and graph search
python agent/agent.py --use_KG --graph-search

# Using Knowledge Graph mode with graph search only
python agent/agent.py --use_KG --graph-search --no-vector-search

# Enable RAG content printing for debugging
python agent/agent.py --use_KG --print-rag
```

### 5.2 Mode Descriptions

- **Embeddings Mode** (default): Uses local embeddings directory for RAG
- **KG Mode with Vector Search**: Uses PostgreSQL vector database for similarity search
- **KG Mode with Graph Search**: Uses Neo4j knowledge graph for relationship-based search
- **KG Mode with Both**: Combines vector and graph search for comprehensive results

### 5.3 Agent Features

The agent supports:
- Reading and writing configuration files
- Running experiment scripts (ESR, find_nv, galvo_scan, optimize)
- Vision analysis of plot images
- RAG-based context retrieval from previous conversations
- Knowledge graph integration for enhanced context understanding

---

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Verify `DATABASE_URL` is correct and accessible
   - Ensure the schema has been applied (run `scheme.sql`)
   - Check that pgvector extension is installed in your PostgreSQL instance

2. **Neo4j Connection Errors**
   - Verify Neo4j is running and accessible
   - Check `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` in `.env`
   - Test connection: `cypher-shell -a bolt://localhost:7687 -u neo4j -p password`

3. **API Key Errors**
   - Ensure all API keys are set in `.env`
   - Verify API keys are valid and have sufficient credits
   - Check that `LLM_API_KEY` and `EMBEDDING_API_KEY` are correctly set

4. **Ingestion Errors**
   - Check that documents directory exists and contains files
   - Verify file permissions
   - Review logs for specific error messages
   - Try running with `--verbose` flag for detailed logging

5. **Import Errors**
   - Ensure all packages from `kg_requirements.txt` are installed
   - Verify Python version compatibility (Python 3.8+)
   - Check that you're running from the correct directory

---

## Next Steps

After completing the setup:

1. **Test the ingestion**: Run a small test with a few documents first
2. **Verify data**: Check that documents and chunks appear in your PostgreSQL database
3. **Check graph**: Query Neo4j to verify knowledge graph relationships were created
4. **Start experimenting**: Run the agent and test RAG functionality

---

## Additional Resources

- **KG Documentation**: See other files in `agent/KG/README_docs/` for detailed explanations:
  - `KG_KNOWLEDGE_STORAGE_EXPLANATION.md`: How knowledge is stored
  - `KG_RELATIONSHIP_TYPES_EXPLANATION.md`: Relationship types in the graph
- **Schema Details**: Review `agent/KG/scheme.sql` for database structure
- **Ingestion Code**: See `agent/KG/ingestion/ingest.py` for ingestion implementation
