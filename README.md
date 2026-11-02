# QueryClarify

Streamlit frontend for the Phase 7 natural language to SQL pipeline.

## Run locally

1. Install dependencies with `python -m pip install -r requirements.txt`.
2. The included `spider_data/` directory is detected automatically. For a dataset stored elsewhere, set `QUERYCLARIFY_DATA_DIR` to its root folder. In PowerShell:

   ```powershell
   $env:QUERYCLARIFY_DATA_DIR = "C:\data\spider_data"
   ```

   The expected layout is `<data folder>\tables.json` and `<data folder>\database\<db_id>\<db_id>.sqlite`.
3. Start the UI with `python -m streamlit run app.py`.

The first query loads `Qwen/Qwen2.5-3B-Instruct` and `all-MiniLM-L6-v2` and may download their weights. If you already have local model folders, set `QUERYCLARIFY_LLM_MODEL` and `QUERYCLARIFY_EMBEDDING_MODEL` to those paths before launching Streamlit. Downloads retry transient DNS/network failures three times and then show a setup message. The app cannot download model weights while the computer cannot resolve or connect to Hugging Face. The SQLite connection runs in read-only mode; generated SQL is not allowed to modify the database.
