
from schema_retrieval import hybrid_scores, select_columns
from schema_linking import expand_relationships
from sql_generator import create_schema_context,clean_sql, generate_sql


def run_pipeline(
    example,
    db,
    embedding_model,
    model,
    tokenizer,
    top_k=5
):
    question = example["question"]

    # Step 1: Retrieve relevant schema columns
    hybrid_results = hybrid_scores(
        question,
        db,
        embedding_model
    )

    selected_columns = select_columns(
        hybrid_results,
        top_k=top_k
    )

    # Step 2: Expand schema using foreign-key relationships
    expanded_columns, relationships = expand_relationships(
        db,
        selected_columns
    )

    # Step 3: Build schema context for the LLM
    schema_context = create_schema_context(
        db,
        expanded_columns,
        relationships
    )

    # Step 4: Generate SQL
    predicted_sql = generate_sql(
        question,
        schema_context,
        model,
        tokenizer
    )

    return {
        "db_id": example["db_id"],
        "question": question,
        "schema_context": schema_context,
        "selected_columns": selected_columns,
        "expanded_columns": expanded_columns,
        "predicted_sql": predicted_sql,
        "gold_sql": example.get("query", "")
    }
