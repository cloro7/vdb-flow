"""Collection service for loading and managing ADR collections."""

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from ..config import Config
    from ..llm.base import LlmProvider

from tqdm import tqdm

from ..constants import DEFAULT_BATCH_SIZE
from ..database.port import (
    VectorDatabase,
    CollectionNotFoundError,
    InvalidCollectionNameError,
    InvalidVectorSizeError,
    unpack_chunk_input,
)
from ..metadata.resolver import (
    content_hash_from_text,
    metadata_for_payload,
    resolve_adr_metadata,
)
from ..validation import (
    validate_collection_name,
    validate_distance_metric,
    validate_path,
)
from .text_processing import clean_text, chunk_text

logger = logging.getLogger(__name__)

# Use constant for batch size
BATCH_SIZE = DEFAULT_BATCH_SIZE


class CollectionService:
    """Service for managing ADR collections."""

    def __init__(
        self,
        db_client: VectorDatabase,
        embedding_func: Callable[[str], List[float]],
        config: Optional["Config"] = None,
        llm_provider: Optional["LlmProvider"] = None,
    ):
        """
        Initialize collection service.

        Args:
            db_client: Vector database client implementing VectorDatabase port
            embedding_func: Text-to-vector embedding (typically ``EmbeddingProvider.embed``,
                wired at the composition root).
            config: Optional Config instance. If None, will use default (for backward compatibility).
            llm_provider: Optional LLM adapter for metadata enrichment (e.g. subprocess CLI).
        """
        self.db_client = db_client
        self._embedding_func = embedding_func
        self._config = config
        self._llm_provider = llm_provider

    def _get_config(self) -> "Config":
        """
        Get configuration instance, using injected config or falling back to default.

        Returns:
            Config instance
        """
        if self._config is not None:
            return self._config
        # Fallback to global config for backward compatibility
        from ..config import get_config

        return get_config()

    @staticmethod
    def _read_file_with_fallback(file_path: str, rel_path: str) -> str:
        """
        Read file with encoding fallback handling.

        Args:
            file_path: Absolute path to the file
            rel_path: Relative path for logging purposes

        Returns:
            File contents as string

        Raises:
            UnicodeDecodeError: If file cannot be read even with fallback
            IOError: If file cannot be opened
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with error handling for files with encoding issues
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
                logger.warning(
                    f"File {rel_path} had encoding issues, "
                    f"replaced invalid characters with replacement markers"
                )
                return text
            except Exception as e:
                logger.error(f"Failed to read file {rel_path}: {e}")
                raise

    def _incremental_unchanged_skip(
        self,
        collection_name: str,
        rel_path: str,
        content_hash: str,
        incremental_lock: threading.Lock,
    ) -> bool:
        """Return True if incremental load should skip this file (content hash unchanged)."""
        filt = {
            "must": [
                {
                    "key": "source_file",
                    "match": {"value": rel_path},
                }
            ]
        }
        with incremental_lock:
            try:
                sample = self.db_client.scroll_points(collection_name, filt, limit=1)
            except NotImplementedError:
                logger.warning(
                    "Incremental load requires scroll_points; loading all files fully"
                )
                sample = []
            if sample:
                prev = sample[0].get("payload") or {}
                if prev.get("content_hash") == content_hash:
                    logger.debug("Skipping unchanged ADR %s", rel_path)
                    return True
            self.db_client.delete_points_by_filter(collection_name, filt)
        return False

    def _preload_one_markdown(
        self,
        collection_name: str,
        file_path: str,
        rel_path: str,
        *,
        do_incremental: bool,
        metadata_enabled: Optional[bool],
        config: "Config",
        incremental_lock: threading.Lock,
    ) -> Optional[Tuple[List[Tuple[str, str, int, Optional[Dict[str, Any]]]], bool]]:
        """
        Read one ADR, resolve metadata, chunk. Used by parallel pre-processing.

        Returns:
            ``(chunk tuples for this file, True)`` on success, or ``None`` if skipped
            (unchanged incremental) or the file could not be read.
        """
        try:
            raw = self._read_file_with_fallback(file_path, rel_path)
        except (UnicodeDecodeError, IOError) as e:
            logger.error(f"Failed to read file {rel_path}: {e}")
            return None
        text = clean_text(raw)
        ch = content_hash_from_text(text)

        if do_incremental and self._incremental_unchanged_skip(
            collection_name, rel_path, ch, incremental_lock
        ):
            return None

        meta_enabled = (
            config.metadata_enabled
            if metadata_enabled is None
            else bool(metadata_enabled)
        )
        if meta_enabled:
            logger.info(
                "Resolving ADR metadata [%s] for %s",
                threading.current_thread().name,
                rel_path,
            )
        meta = resolve_adr_metadata(
            config,
            file_path,
            rel_path,
            text,
            self._llm_provider,
            metadata_enabled=metadata_enabled,
        )
        if meta_enabled and meta:
            title = meta.get("title") or ""
            if len(title) > 120:
                title = title[:117] + "..."
            logger.info(
                "Resolved metadata [%s] for %s: adr_id=%r title=%r code_scope=%s "
                "repo_type=%s tags=%s source=%s",
                threading.current_thread().name,
                rel_path,
                meta.get("adr_id"),
                title,
                meta.get("code_scope"),
                meta.get("repo_type"),
                meta.get("tags"),
                meta.get("metadata_source"),
            )
        meta_payload = metadata_for_payload(meta)
        chunks = chunk_text(text)
        out: List[Tuple[str, str, int, Optional[Dict[str, Any]]]] = []
        for i, chunk in enumerate(chunks):
            out.append((chunk, rel_path, i + 1, meta_payload))
        return (out, True)

    def create_collection(
        self,
        collection_name: str,
        distance_metric: str = "Cosine",
        enable_hybrid: bool = True,
        vector_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a new collection.

        Args:
            collection_name: Name of the collection
            distance_metric: Distance metric to use (Cosine, Euclid, Dot)
            enable_hybrid: Enable hybrid search with sparse vectors
            vector_size: Size of embedding vectors (defaults to config value)

        Returns:
            Collection information

        Raises:
            InvalidCollectionNameError: If collection name is invalid
            InvalidVectorSizeError: If vector size is invalid
        """
        try:
            validate_collection_name(collection_name)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e

        validate_distance_metric(distance_metric)

        # Get vector size from config if not provided
        if vector_size is None:
            config = self._get_config()
            vector_size = config.vector_size

        # Validate vector size is positive
        if vector_size <= 0:
            raise InvalidVectorSizeError(
                f"vector_size must be positive, got {vector_size}. "
                f"Vector dimensions must be greater than zero."
            )

        return self.db_client.create_collection(
            collection_name,
            distance_metric,
            vector_size=vector_size,
            enable_hybrid=enable_hybrid,
        )

    def delete_collection(self, collection_name: str) -> None:
        """
        Delete an existing collection.

        Args:
            collection_name: Name of the collection to delete

        Raises:
            InvalidCollectionNameError: If collection name is invalid
        """
        try:
            validate_collection_name(collection_name)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e
        self.db_client.delete_collection(collection_name)

    def clear_collection(self, collection_name: str) -> Dict[str, Any]:
        """
        Clear all points from a collection without deleting it.

        Args:
            collection_name: Name of the collection

        Returns:
            Operation result

        Raises:
            InvalidCollectionNameError: If collection name is invalid
        """
        try:
            validate_collection_name(collection_name)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e
        return self.db_client.clear_collection(collection_name)

    def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all collections.

        Returns:
            List of collection information
        """
        collections = self.db_client.list_collections()
        return collections

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get information about a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Collection information

        Raises:
            InvalidCollectionNameError: If collection name is invalid
        """
        try:
            validate_collection_name(collection_name)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e
        return self.db_client.get_collection_info(collection_name)

    def _validate_collection_exists(self, collection_name: str) -> None:
        """
        Validate that collection exists before loading.

        Args:
            collection_name: Name of the collection to validate

        Raises:
            ValueError: If collection does not exist
        """
        try:
            collection_info = self.db_client.get_collection_info(collection_name)
            if not collection_info or not collection_info.get("result"):
                raise ValueError(
                    f"Collection '{collection_name}' does not exist. "
                    f"Please create it first using the 'create' command."
                )
        except CollectionNotFoundError:
            raise ValueError(
                f"Collection '{collection_name}' does not exist. "
                f"Please create it first using the 'create' command."
            )

    def _list_markdown_files(self, validated_path: Path) -> List[Tuple[str, str]]:
        """Discover all ``.md`` files under ``validated_path``."""
        md_files: List[Tuple[str, str]] = []
        path_str = str(validated_path)
        for root, _, files in os.walk(path_str):
            for file in files:
                if file.endswith(".md"):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, path_str)
                    md_files.append((file_path, rel_path))
        return md_files

    def _process_batch_with_fallback(
        self,
        collection_name: str,
        batch: List[Tuple[str, str, int]],
        pbar: Any,
    ) -> int:
        """
        Process a batch of chunks with fallback to individual uploads.

        Args:
            collection_name: Name of the collection
            batch: List of tuples (chunk_text, file_name, chunk_id)
            pbar: Progress bar to update

        Returns:
            Number of successfully processed chunks
        """
        processed = 0

        # Progress callback to update progress bar incrementally
        def progress_callback(count: int) -> None:
            pbar.update(count)
            pbar.refresh()  # Force immediate refresh

        try:
            self.db_client.upload_chunks_batch(
                collection_name,
                batch,
                self._embedding_func,
                progress_callback=progress_callback,
            )
            processed = len(batch)
        except Exception as e:
            logger.warning(
                f"Batch upload failed, falling back to individual uploads: {e}"
            )
            # Fallback to individual uploads for this batch
            for item in batch:
                chunk_content, file_name, chunk_id, adr_meta = unpack_chunk_input(item)
                try:
                    self.db_client.upload_chunk(
                        collection_name,
                        chunk_content,
                        file_name,
                        chunk_id,
                        self._embedding_func,
                        adr_metadata=adr_meta,
                    )
                    processed += 1
                    pbar.update(1)
                    pbar.refresh()  # Force immediate refresh
                except Exception as e2:
                    logger.error(f"Failed to upload chunk {file_name}-{chunk_id}: {e2}")
        return processed

    def load_collection(
        self,
        collection_name: str,
        path: str,
        *,
        incremental: Optional[bool] = None,
        metadata_enabled: Optional[bool] = None,
    ) -> None:
        """
        Recursively read all .md ADRs from path, chunk them, and upload.

        Pre-processing (read → metadata → chunk) runs in parallel using a thread pool
        sized by config ``metadata.preprocess_workers`` (default 4). Set to ``1`` to
        process one file at a time. This speeds up slow metadata steps (e.g. LLM
        subprocess calls) without requiring a full asyncio stack.

        Args:
            collection_name: Name of the collection
            path: Path to ADR directory (can include subfolders)
            incremental: If True, skip unchanged ADRs (content hash) and replace only
                changed files. Defaults to config ``metadata.incremental``.
            metadata_enabled: If False, do not resolve or store ADR metadata payloads.
                Defaults to config ``metadata.enabled``.

        Raises:
            ValueError: If collection does not exist or validation fails
            FileNotFoundError: If path does not exist
            UnicodeDecodeError: If file encoding cannot be handled
        """
        # Validate inputs
        try:
            validate_collection_name(collection_name)
        except ValueError as e:
            raise InvalidCollectionNameError(str(e)) from e
        # Get restricted paths and glob patterns from config if available
        config = self._get_config()
        restricted_paths = getattr(config, "restricted_paths", None)
        denied_patterns = getattr(config, "denied_patterns", None) if config else None
        allowed_patterns = getattr(config, "allowed_patterns", None) if config else None
        validated_path = validate_path(
            path,
            must_exist=True,
            restricted_paths=restricted_paths,
            warn_on_optional=True,
            denied_patterns=denied_patterns,
            allowed_patterns=allowed_patterns,
        )

        # Validate that collection exists
        self._validate_collection_exists(collection_name)

        do_incremental = (
            config.metadata_incremental if incremental is None else incremental
        )
        md_paths = self._list_markdown_files(validated_path)
        if not md_paths:
            logger.warning(f"No .md files found in {path}")
            return

        n_md = len(md_paths)
        workers = config.metadata_preprocess_workers
        logger.info(
            "Pre-processing %d markdown file(s) using %d thread(s): "
            "read → metadata → chunk (see progress bar).",
            n_md,
            workers,
        )

        all_chunks: List[Tuple[str, str, int, Optional[Dict[str, Any]]]] = []
        files_loaded = 0

        incremental_lock = threading.Lock()

        def _preload_task(
            item: Tuple[str, str],
        ) -> Optional[
            Tuple[List[Tuple[str, str, int, Optional[Dict[str, Any]]]], bool]
        ]:
            fp, rp = item
            return self._preload_one_markdown(
                collection_name,
                fp,
                rp,
                do_incremental=do_incremental,
                metadata_enabled=metadata_enabled,
                config=config,
                incremental_lock=incremental_lock,
            )

        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(
                tqdm(
                    ex.map(_preload_task, md_paths),
                    total=n_md,
                    desc="Pre-processing files",
                    unit="file",
                    leave=True,
                    bar_format=(
                        "{l_bar}{bar}| {n_fmt}/{total_fmt} files "
                        "[{elapsed}<{remaining}, {rate_fmt}]"
                    ),
                )
            )

        for result in results:
            if result is None:
                continue
            chunk_rows, _loaded = result
            all_chunks.extend(chunk_rows)
            files_loaded += 1

        if not all_chunks:
            logger.warning(f"No chunkable content in {path}")
            return

        total_chunks = len(all_chunks)
        logger.info(
            "Pre-processing done: %d file(s), %d chunk(s). Starting embeddings and upload.",
            files_loaded,
            total_chunks,
        )

        # Process chunks in batches with parallel embedding generation
        with tqdm(
            total=len(all_chunks),
            desc="Processing chunks",
            unit="chunk",
            leave=True,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} chunks [{elapsed}<{remaining}, {rate_fmt}]",
        ) as pbar:
            for batch_start in range(0, len(all_chunks), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(all_chunks))
                batch = all_chunks[batch_start:batch_end]
                self._process_batch_with_fallback(collection_name, batch, pbar)

        logger.debug(
            f"Successfully loaded {files_loaded} files ({total_chunks} chunks) "
            f"into collection '{collection_name}'"
        )
