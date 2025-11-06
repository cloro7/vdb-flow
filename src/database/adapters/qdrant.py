"""Qdrant database adapter for hexagonal architecture."""
import logging
import requests
import uuid
import hashlib
from typing import List, Dict, Any, Callable

from ..port import VectorDatabase

logger = logging.getLogger(__name__)


class QdrantVectorDatabase(VectorDatabase):
    """Qdrant implementation of VectorDatabase port."""
    
    def __init__(self, qdrant_url: str = "http://localhost:6333"):
        """
        Initialize Qdrant vector database client.
        
        Args:
            qdrant_url: Base URL for Qdrant instance
        """
        self.qdrant_url = qdrant_url.rstrip("/")
        self._hybrid_collections_cache: Dict[str, bool] = {}
    
    def create_collection(
        self, 
        collection_name: str, 
        distance_metric: str = "Cosine", 
        vector_size: int = 768,
        enable_hybrid: bool = True
    ) -> Dict[str, Any]:
        """
        Create a new collection in Qdrant.
        
        Args:
            collection_name: Name of the collection
            distance_metric: Distance metric (Cosine, Euclid, Dot)
            vector_size: Size of the dense vectors
            enable_hybrid: Enable hybrid search with sparse vectors
        """
        url = f"{self.qdrant_url}/collections/{collection_name}"
        
        if enable_hybrid:
            # Create collection with named vectors for hybrid search
            # dense: for semantic search
            # text: for keyword-based search (BM25) - matches MCP server expectation
            payload = {
                "vectors": {
                    "dense": {
                        "size": vector_size,
                        "distance": distance_metric
                    }
                },
                "sparse_vectors": {
                    "text": {}  # Sparse vector configuration for BM25
                }
            }
            logger.info(f"Creating collection '{collection_name}' with hybrid search enabled.")
        else:
            # Create standard collection with single dense vector
            payload = {
                "vectors": {
                    "size": vector_size,
                    "distance": distance_metric
                }
            }
            logger.info(f"Creating collection '{collection_name}' with semantic search only.")
        
        resp = requests.put(url, json=payload)
        if resp.status_code == 200:
            # Cache hybrid status for the new collection
            self._hybrid_collections_cache[collection_name] = enable_hybrid
            logger.info(f"Created collection '{collection_name}'.")
            return resp.json()
        else:
            logger.warning(f"Failed to create collection: {resp.status_code} — {resp.text}")
            return {}
    
    def delete_collection(self, collection_name: str) -> None:
        """Manually delete a Qdrant collection."""
        url = f"{self.qdrant_url}/collections/{collection_name}"
        resp = requests.delete(url)
        if resp.status_code == 200:
            # Clear cache for deleted collection
            self._hybrid_collections_cache.pop(collection_name, None)
            logger.info(f"Deleted collection '{collection_name}'")
        elif resp.status_code == 404:
            # Clear cache even if collection not found
            self._hybrid_collections_cache.pop(collection_name, None)
            logger.info(f"Collection '{collection_name}' not found.")
        else:
            logger.warning(f"Failed to delete {collection_name}: {resp.status_code} — {resp.text}")
    
    def clear_collection(self, collection_name: str) -> Dict[str, Any]:
        """Delete all points from a collection without deleting the collection."""
        url = f"{self.qdrant_url}/collections/{collection_name}/points/delete"
        resp = requests.post(url, json={"filter": {}})
        if resp.status_code == 200:
            logger.info(f"Cleared all points from collection '{collection_name}'.")
            return resp.json()
        else:
            logger.warning(f"Failed to clear collection '{collection_name}': {resp.status_code} — {resp.text}")
            return {}
    
    def list_collections(self) -> List[Dict[str, Any]]:
        """List all collections in Qdrant."""
        url = f"{self.qdrant_url}/collections"
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json().get("result", {}).get("collections", [])
        else:
            logger.warning(f"Failed to list collections: {resp.status_code} — {resp.text}")
            return []
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get information about a collection in Qdrant."""
        url = f"{self.qdrant_url}/collections/{collection_name}"
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.warning(f"Failed to get collection info: {resp.status_code} — {resp.text}")
            return {}
    
    def upload_chunk(
        self,
        collection: str,
        chunk_text: str,
        file_name: str,
        chunk_id: int,
        embedding_func: Callable[[str], List[float]]
    ) -> None:
        """
        Upload one chunk to Qdrant if it doesn't already exist.
        
        Args:
            collection: Collection name
            chunk_text: Text content of the chunk
            file_name: Source file name
            chunk_id: Chunk identifier
            embedding_func: Function to generate embeddings (takes text, returns vector)
        """
        # Create deterministic UUID from file name + chunk number
        point_id = str(uuid.UUID(hashlib.md5(f"{file_name}-{chunk_id}".encode()).hexdigest()))
        
        # Check if this point already exists
        check_url = f"{self.qdrant_url}/collections/{collection}/points/{point_id}"
        check_resp = requests.get(check_url)
        if check_resp.status_code == 200:
            logger.debug(f"Skipping existing chunk {file_name}-{chunk_id}")
            return
        
        # Generate embedding
        vector = embedding_func(chunk_text)
        
        # Check if collection uses named vectors (hybrid search)
        # Cache the result to avoid checking on every upload
        if collection not in self._hybrid_collections_cache:
            collection_info = self.get_collection_info(collection)
            # Collection info structure: {"result": {"config": {"params": {...}}}}
            result = collection_info.get("result", {})
            config = result.get("config", {})
            params = config.get("params", {})
            
            # Check for sparse_vectors (indicates hybrid)
            has_sparse = bool(params.get("sparse_vectors"))
            
            # Check if vectors is a dict with named vectors (indicates hybrid)
            # Standard: {"size": 768, "distance": "Cosine"}
            # Hybrid: {"dense": {"size": 768, "distance": "Cosine"}}
            vectors_config = params.get("vectors", {})
            has_named_vectors = (
                isinstance(vectors_config, dict) and 
                "dense" in vectors_config  # Explicit check for "dense" named vector
            )
            
            is_hybrid = has_sparse or has_named_vectors
            
            self._hybrid_collections_cache[collection] = is_hybrid
            logger.info(
                f"Collection '{collection}' hybrid detection: "
                f"sparse_vectors={has_sparse}, named_vectors={has_named_vectors}, is_hybrid={is_hybrid}"
            )
        else:
            is_hybrid = self._hybrid_collections_cache[collection]
        
        # Format vector based on collection type
        if is_hybrid:
            # Hybrid collection: use named vector "dense"
            vector_payload = {"dense": vector}
            logger.debug(f"Using named vector format for hybrid collection")
        else:
            # Standard collection: use unnamed vector
            vector_payload = vector
            logger.debug(f"Using unnamed vector format for standard collection")
        
        payload = {
            "text": chunk_text,
            "source_file": file_name,
            "chunk_id": chunk_id
        }
        
        data = {"points": [{"id": point_id, "vector": vector_payload, "payload": payload}]}
        resp = requests.put(
            f"{self.qdrant_url}/collections/{collection}/points?wait=true",
            json=data
        )
        if not resp.ok:
            logger.error(f"Upload failed for {file_name}-{chunk_id}: {resp.status_code} — {resp.text}")
        else:
            logger.info(f"Uploaded chunk {file_name}-{chunk_id}")
    
    def search(
        self,
        collection_name: str,
        vector: List[float],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors in Qdrant collection.
        
        Args:
            collection_name: Name of the collection to search
            vector: Query vector
            limit: Maximum number of results
            
        Returns:
            List of search results with score and payload
        """
        search_url = f"{self.qdrant_url}/collections/{collection_name}/points/search"
        search_data = {
            "vector": vector,
            "limit": limit,
            "with_payload": True,
            "with_vector": False
        }
        
        try:
            resp = requests.post(search_url, json=search_data)
            if resp.status_code == 200:
                results = resp.json().get("result", [])
                return results
            else:
                logger.warning(f"Failed to search: {resp.status_code} — {resp.text}")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching: {e}")
            return []

