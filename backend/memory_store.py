import os
import sqlite3
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Set

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer


@dataclass
class LabeledEmail:
    message_id: str
    subject: Optional[str]
    sender: Optional[str]
    snippet: Optional[str]
    applied_label: str
    accepted: bool


class MemoryStore:
    """Persist labeled emails and provide simple vector search over them."""

    def __init__(self, data_dir: str) -> None:
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, "memory.db")
        self.index_path = os.path.join(self.data_dir, "faiss.index")
        
        # Initialize logger
        self.logger = logging.getLogger("gmail_labeler")
        
        # Set dimension to match the model's output (384 for all-MiniLM-L6-v2)
        self.dim: int = 384
        
        # Initialize the sentence transformer model
        try:
            self.logger.info("Loading sentence transformer model...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.logger.info("Sentence transformer model loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load sentence transformer model: {e}")
            self.model = None
        
        # Use check_same_thread=False to allow cross-thread access
        # NOTE: We initialize the connection AFTER loading the model to avoid thread issues
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()
        self.index: Optional[faiss.IndexFlatIP] = None
        self._load_or_init_index()

    def _init_db(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS labeled_emails (
                message_id TEXT PRIMARY KEY,
                subject TEXT,
                sender TEXT,
                snippet TEXT,
                applied_label TEXT NOT NULL,
                accepted INTEGER NOT NULL CHECK (accepted IN (0,1))
            )
            """
        )
        # New table for rejected labels to avoid suggesting them again for similar emails
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS rejected_labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL,
                subject TEXT,
                sender TEXT,
                snippet TEXT,
                rejected_label TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()

    def _load_or_init_index(self) -> None:
        # Using cosine similarity via inner product on normalized vectors
        self.index = faiss.IndexFlatIP(self.dim)
        if os.path.exists(self.index_path) and os.path.getsize(self.index_path) > 0:
            self.index = faiss.read_index(self.index_path)

    def _save_index(self) -> None:
        if self.index is not None:
            faiss.write_index(self.index, self.index_path)

    def _embed(self, text: str) -> np.ndarray:
        """Generate embeddings using the sentence transformer model or fallback to deterministic hash."""
        if not text:
            # Handle empty text
            return np.zeros(self.dim, dtype="float32")
        
        try:
            if self.model is not None:
                # Use sentence transformer model
                embedding = self.model.encode(text, convert_to_numpy=True)
                # No need to resize since we've set self.dim to match the model's output dimension
                
                # Normalize to unit length
                norm = np.linalg.norm(embedding) + 1e-8
                embedding = embedding / norm
                return embedding.astype("float32")
        except Exception as e:
            self.logger.error(f"Error generating embedding with model: {e}")
            # Fall through to fallback method
        
        # Fallback: deterministic hashing
        self.logger.info("Using fallback embedding method")
        rng = np.random.default_rng(abs(hash(text)) % (2**32))
        vec = rng.normal(size=(self.dim,)).astype("float32")
        norm = np.linalg.norm(vec) + 1e-8
        vec = vec / norm
        return vec

    # Public exposure for the embedding function so classifier can reuse it
    def embed_text(self, text: str) -> np.ndarray:
        return self._embed(text)

    def get_label_centroids(self) -> Dict[str, np.ndarray]:
        """Compute centroids (mean embeddings) per applied_label for accepted rows.
        
        Prioritizes accepted labels (user-approved) with higher weights.
        Returns a mapping: label -> 1D np.ndarray of shape (dim,)
        """
        cur = self.conn.cursor()
        # Get all labeled emails but track which ones were explicitly accepted
        cur.execute(
            "SELECT applied_label, subject, sender, snippet, accepted FROM labeled_emails"
        )
        rows = cur.fetchall()
        if not rows:
            return {}
            
        accum: Dict[str, List[Tuple[np.ndarray, float]]] = {}  # (embedding, weight)
        for applied_label, subject, sender, snippet, accepted in rows:
            joined = " \n ".join([x for x in [subject, sender, snippet] if x])
            emb = self._embed(joined)
            # Give higher weight (5x) to user-approved labels for stronger reinforcement
            weight = 5.0 if accepted else 1.0
            accum.setdefault(applied_label, []).append((emb, weight))
            
        centroids: Dict[str, np.ndarray] = {}
        for label, vec_weights in accum.items():
            if not vec_weights:
                continue
                
            # Calculate weighted average
            vecs = [v for v, _ in vec_weights]
            weights = np.array([w for _, w in vec_weights])
            weights = weights / weights.sum()  # Normalize weights
            
            # Stack vectors and apply weights
            mat = np.vstack(vecs)
            weighted_mean = np.average(mat, axis=0, weights=weights)
            
            # Normalize to unit length
            norm = np.linalg.norm(weighted_mean) + 1e-8
            centroids[label] = (weighted_mean / norm).astype("float32")
            
        return centroids

    def upsert_labeled_email(self, email: LabeledEmail) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO labeled_emails (message_id, subject, sender, snippet, applied_label, accepted)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE SET
                subject=excluded.subject,
                sender=excluded.sender,
                snippet=excluded.snippet,
                applied_label=excluded.applied_label,
                accepted=excluded.accepted
            """,
            (
                email.message_id,
                email.subject,
                email.sender,
                email.snippet,
                email.applied_label,
                1 if email.accepted else 0,
            ),
        )
        self.conn.commit()

        # Update vector index. For simplicity, rebuild on each upsert for prototype size.
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        cur = self.conn.cursor()
        cur.execute("SELECT message_id, subject, sender, snippet FROM labeled_emails WHERE accepted=1")
        rows = cur.fetchall()
        if not rows:
            self.index = faiss.IndexFlatIP(self.dim)
            self._save_index()
            return
        texts = []
        self.ids: List[str] = []
        for message_id, subject, sender, snippet in rows:
            self.ids.append(message_id)
            joined = " \n ".join([x for x in [subject, sender, snippet] if x])
            texts.append(joined)
        embeddings = np.vstack([self._embed(t) for t in texts])
        self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(embeddings)
        self._save_index()

    def similar(self, subject: Optional[str], sender: Optional[str], snippet: Optional[str], k: int = 5) -> List[Tuple[str, float]]:
        """Return top k (message_id, score) similar accepted emails."""
        if self.index is None or self.index.ntotal == 0:
            return []
        joined = " \n ".join([x for x in [subject, sender, snippet] if x])
        q = self._embed(joined)
        q = q.reshape(1, -1)
        scores, idxs = self.index.search(q, min(k, max(1, self.index.ntotal)))
        results: List[Tuple[str, float]] = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            msg_id = getattr(self, "ids", [])[idx] if idx < len(getattr(self, "ids", [])) else None
            if msg_id:
                results.append((msg_id, float(score)))
        return results

    def get_label_for_message(self, message_id: str) -> Optional[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT applied_label FROM labeled_emails WHERE message_id=?", (message_id,))
        row = cur.fetchone()
        return row[0] if row else None

    def get_messages_by_ids(self, ids: List[str]) -> List[Dict]:
        if not ids:
            return []
        placeholders = ",".join(["?"] * len(ids))
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT message_id, subject, sender, snippet, applied_label, accepted FROM labeled_emails WHERE message_id IN ({placeholders})",
            ids,
        )
        rows = cur.fetchall()
        out: List[Dict] = []
        for message_id, subject, sender, snippet, applied_label, accepted in rows:
            out.append(
                {
                    "message_id": message_id,
                    "subject": subject,
                    "sender": sender,
                    "snippet": snippet,
                    "applied_label": applied_label,
                    "accepted": bool(accepted),
                }
            )
        return out

    def get_processed_email_ids(self) -> set:
        """Get all email IDs that have been processed (approved or rejected)."""
        cur = self.conn.cursor()
        cur.execute("SELECT DISTINCT message_id FROM labeled_emails")
        rows = cur.fetchall()
        return {row[0] for row in rows}

    def mark_email_processed(self, message_id: str, applied_label: str, accepted: bool = True):
        """Mark an email as processed with its label."""
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO labeled_emails (message_id, subject, sender, snippet, applied_label, accepted) VALUES (?, ?, ?, ?, ?, ?)",
            (message_id, None, None, None, applied_label, accepted)
        )
        self.conn.commit()
        logger.info(f"Marked email {message_id} as processed with label '{applied_label}' (accepted: {accepted})")

    def store_rejected_label(self, message_id: str, subject: str, sender: str, snippet: str, rejected_label: str) -> None:
        """Store a rejected label to avoid suggesting it again for similar emails."""
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO rejected_labels (message_id, subject, sender, snippet, rejected_label)
            VALUES (?, ?, ?, ?, ?)
            """,
            (message_id, subject, sender, snippet, rejected_label)
        )
        self.conn.commit()
        logger.info(f"Stored rejected label '{rejected_label}' for email {message_id}")

    def get_rejected_labels_for_similar_emails(self, subject: str, sender: str, snippet: str, similarity_threshold: float = 0.7) -> Set[str]:
        """Get labels that were rejected for similar emails to avoid suggesting them again."""
        cur = self.conn.cursor()
        cur.execute("SELECT subject, sender, snippet, rejected_label FROM rejected_labels")
        rows = cur.fetchall()
        
        if not rows:
            return set()
        
        # Create embedding for the current email
        current_text = " \n ".join([x for x in [subject, sender, snippet] if x])
        current_embedding = self._embed(current_text)
        
        rejected_labels = set()
        for stored_subject, stored_sender, stored_snippet, rejected_label in rows:
            # Create embedding for stored rejected email
            stored_text = " \n ".join([x for x in [stored_subject, stored_sender, stored_snippet] if x])
            stored_embedding = self._embed(stored_text)
            
            # Calculate similarity
            similarity = np.dot(current_embedding, stored_embedding) / (
                np.linalg.norm(current_embedding) * np.linalg.norm(stored_embedding)
            )
            
            # If similar enough, add the rejected label to avoid list
            if similarity >= similarity_threshold:
                rejected_labels.add(rejected_label)
                logger.info(f"Found similar rejected email (similarity: {similarity:.2f}), avoiding label '{rejected_label}'")
        
        return rejected_labels
