"""Runtime setup and safe SQLite execution for the Streamlit app."""

import json
import os
import sqlite3
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _find_data_dir():
    configured = os.getenv("QUERYCLARIFY_DATA_DIR")
    candidates = [Path(configured)] if configured else []
    candidates += [BASE_DIR / "spider_data", BASE_DIR / "data" / "spider_data"]
    for candidate in candidates:
        if (candidate / "tables.json").is_file() and (candidate / "database").is_dir():
            return candidate.resolve()
    return None


def data_status():
    data_dir = _find_data_dir()
    if data_dir is None:
        return None, "Set QUERYCLARIFY_DATA_DIR to the Spider data folder containing tables.json and database/."
    return data_dir, None


def load_schemas(data_dir):
    with (Path(data_dir) / "tables.json").open(encoding="utf-8") as f:
        schemas = json.load(f)
    return {item["db_id"]: item for item in schemas}


def _load_with_network_retries(label, loader, attempts=3):
    """Retry transient Hub failures and report DNS/network errors clearly."""
    for attempt in range(attempts):
        try:
            return loader()
        except Exception as exc:
            message = str(exc)
            lowered = message.lower()
            is_network_error = any(
                marker in lowered
                for marker in (
                    "getaddrinfo failed", "name or service not known",
                    "temporary failure in name resolution", "connection error",
                    "timed out", "network is unreachable",
                )
            )
            if not is_network_error:
                raise
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(
                f"Could not download {label} from Hugging Face after "
                f"{attempts} attempts because this computer could not reach "
                "the model server (DNS/network error). Check that the computer "
                "has internet access and can resolve huggingface.co, then "
                "restart the app and retry. You can also set the corresponding "
                "QUERYCLARIFY_*_MODEL environment variable to a local model folder."
            ) from exc


def load_pipeline_resources(data_dir, llm_name, embedding_name):
    """Load schemas and the same model families used by the Phase 7 notebook."""
    from sentence_transformers import SentenceTransformer
    from transformers import AutoModelForCausalLM, AutoTokenizer

    schema_lookup = load_schemas(data_dir)
    if not schema_lookup:
        raise RuntimeError("tables.json does not contain any database schemas.")

    tokenizer = _load_with_network_retries(
        "the language model tokenizer",
        lambda: AutoTokenizer.from_pretrained(llm_name),
    )
    model = _load_with_network_retries(
        "the language model weights",
        lambda: AutoModelForCausalLM.from_pretrained(
            llm_name, torch_dtype="auto", device_map="auto"
        ),
    )
    embedding_model = _load_with_network_retries(
        "the embedding model",
        lambda: SentenceTransformer(embedding_name),
    )

    # Add src to import path because the existing pipeline modules use flat imports.
    import sys
    src_dir = str(BASE_DIR / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from phase7_pipeline import continue_query, start_query

    return schema_lookup, model, tokenizer, embedding_model, start_query, continue_query


def execute_readonly(database_dir, db_id, sql, limit=500):
    """Execute one generated statement against its SQLite file in read-only mode."""
    db_path = Path(database_dir) / db_id / f"{db_id}.sqlite"
    if not db_path.is_file():
        raise FileNotFoundError(f"SQLite database not found for '{db_id}'.")

    uri = db_path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=10) as conn:
        conn.execute("PRAGMA query_only = ON")
        cursor = conn.execute(sql)
        if cursor.description is None:
            raise ValueError("Generated SQL did not return a result set.")
        columns = [item[0] for item in cursor.description]
        rows = cursor.fetchmany(limit + 1)
    return columns, rows[:limit], len(rows) > limit
