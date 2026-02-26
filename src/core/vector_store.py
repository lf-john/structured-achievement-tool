"""
VectorStore for storing and searching document embeddings.

This module uses sqlite-vec for efficient similarity search on
document embeddings.
"""

import sqlite3
import json
from typing import List, Dict, Any, Optional
import sqlite_vec
from src.core.embedding_service import EmbeddingService


class VectorStore:
    """
    Vector database for storing and searching document embeddings.

    Uses sqlite-vec for efficient similarity search and SQLite for
    storing document metadata.
    """

    def __init__(self, db_path: str, embedding_service: EmbeddingService, dimension: Optional[int] = None):
        """
        Initialize the VectorStore.

        Args:
            db_path: Path to the SQLite database file.
            embedding_service: Service for generating embeddings.
            dimension: Dimension of embedding vectors. If None, will be determined
                      from the first embedding.
        """
        self.db_path = db_path
        self.embedding_service = embedding_service
        self.dimension = dimension
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")

        # Enable sqlite-vec extension
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)

        self._create_tables()

    def _create_tables(self):
        """Create the necessary database tables if they don't exist."""
        cursor = self.conn.cursor()

        # Create documents table for storing text and metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Check if vec_documents table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='vec_documents'
        """)
        table_exists = cursor.fetchone() is not None

        # Only create vec_documents if it doesn't exist and we have dimension info
        if not table_exists and self.dimension is not None:
            cursor.execute(f"""
                CREATE VIRTUAL TABLE vec_documents USING vec0(
                    doc_id INTEGER PRIMARY KEY,
                    embedding FLOAT[{self.dimension}]
                )
            """)

        self.conn.commit()

    def add_document(self, text: str, metadata: Dict[str, Any]) -> int:
        """
        Add a document to the vector store.

        Args:
            text: The text content of the document.
            metadata: Dictionary of metadata to store with the document.

        Returns:
            The ID of the inserted document.
        """
        # Generate embedding for the text
        embedding = self.embedding_service.embed_text(text)

        # Initialize dimension and create vec table if needed
        if self.dimension is None:
            self.dimension = len(embedding)
            self._create_vec_table()

        # Store the document
        cursor = self.conn.cursor()

        # Insert document text and metadata
        metadata_json = json.dumps(metadata)
        cursor.execute(
            "INSERT INTO documents (text, metadata) VALUES (?, ?)",
            (text, metadata_json)
        )
        doc_id = cursor.lastrowid

        # Store the embedding vector
        # Convert embedding to bytes for storage
        embedding_blob = self._serialize_embedding(embedding)
        cursor.execute(
            "INSERT INTO vec_documents (doc_id, embedding) VALUES (?, ?)",
            (doc_id, embedding_blob)
        )

        self.conn.commit()
        return doc_id

    def _create_vec_table(self):
        """Create the vector table if it doesn't exist."""
        cursor = self.conn.cursor()

        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='vec_documents'
        """)
        table_exists = cursor.fetchone() is not None

        if not table_exists and self.dimension is not None:
            cursor.execute(f"""
                CREATE VIRTUAL TABLE vec_documents USING vec0(
                    doc_id INTEGER PRIMARY KEY,
                    embedding FLOAT[{self.dimension}]
                )
            """)
            self.conn.commit()

    def search(self, query_text: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for documents similar to the query text.

        Args:
            query_text: The text to search for.
            k: Maximum number of results to return.

        Returns:
            A list of dictionaries containing:
                - text: The document text
                - metadata: The document metadata
                - score: Similarity score (lower distance = higher similarity)
                - id: Document ID
        """
        # Handle empty query text
        if not query_text or not query_text.strip():
            return []

        # Generate embedding for the query
        query_embedding = self.embedding_service.embed_text(query_text)
        query_blob = self._serialize_embedding(query_embedding)

        # Query for similar vectors using sqlite-vec
        cursor = self.conn.cursor()

        # First check if there are any documents
        cursor.execute("SELECT COUNT(*) FROM documents")
        count = cursor.fetchone()[0]
        if count == 0:
            return []

        # Perform vector similarity search
        # sqlite-vec uses cosine distance by default
        cursor.execute("""
            SELECT
                d.id,
                d.text,
                d.metadata,
                vec_distance_cosine(v.embedding, ?) as distance
            FROM vec_documents v
            JOIN documents d ON d.id = v.doc_id
            ORDER BY distance ASC
            LIMIT ?
        """, (query_blob, k))

        results = []
        for row in cursor.fetchall():
            doc_id, text, metadata_json, distance = row
            metadata = json.loads(metadata_json) if metadata_json else {}

            results.append({
                "id": doc_id,
                "text": text,
                "metadata": metadata,
                "score": 1.0 - distance,  # Convert distance to similarity score
                "distance": distance
            })

        return results

    def _serialize_embedding(self, embedding: List[float]) -> bytes:
        """
        Serialize an embedding vector to bytes for storage.

        Args:
            embedding: List of floats representing the embedding.

        Returns:
            Serialized bytes representation.
        """
        # sqlite-vec expects a specific format
        # We'll use the JSON serialization that sqlite-vec can handle
        import struct

        # Pack floats as binary data
        return struct.pack(f'{len(embedding)}f', *embedding)

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def __del__(self):
        """Cleanup database connection on deletion."""
        self.close()
