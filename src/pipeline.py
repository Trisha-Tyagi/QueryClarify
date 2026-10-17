
from schema_retrieval import hybrid_scores, select_columns
from schema_linking import expand_relationships
from sql_generator import create_schema_context, generate_sql


def run_pipeline(example, db, embedding_model, model, tokenizer, top_k=5):
    question = example["question"]

    # 1. Lexical + semantic + hybrid scoring
    hybrid_results = hybrid_scores(
        question, db, embedding_model
    )

    # 2. Select relevant columns
    selected_columns = select_columns(
        hybrid_results, top_k=top_k
    )

    # 3. Expand columns and retrieve relationships
    expanded_columns, relationships = expand_relationships(
        db, selected_columns
    )

    # 4. Create reduced schema context
    schema_context = create_schema_context(
        db, expanded_columns, relationships
    )

    # 5. Generate SQL using Qwen
    predicted_sql = generate_sql(
        question, schema_context, model, tokenizer
    )

    # 6. Return result fields
    return {
        "db_id": example["db_id"],
        "question": question,
        "schema_context": schema_context,
        "predicted_sql": predicted_sql,
        "gold_sql": example["query"]
    }
