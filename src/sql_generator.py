
def create_schema_context(db, selected_columns, relationships):
    schema_text = f"Database: {db['db_id']}\n\n"
    schema_text += "Relevant Tables and Columns:\n"

    for table_idx, table in enumerate(db["table_names_original"]):
        table_columns = []

        for col_idx, column in enumerate(db["column_names"]):
            if column[0] != table_idx or column[1] == "*":
                continue

            # Name used by retrieval
            normalized_name = (
                f"{db['table_names'][table_idx]}.{column[1]}"
            )

            # Original column name used for SQL generation
            original_name = db["column_names_original"][col_idx][1]

            if normalized_name in selected_columns:
                table_columns.append(original_name)

        if table_columns:
            schema_text += f"\nTable: {table}\n"

            for column in table_columns:
                schema_text += f"- {column}\n"

    if relationships:
        schema_text += "\nRelationships:\n"

        for relationship in relationships:
            schema_text += f"- {relationship}\n"

    return schema_text




import torch


def generate_sql(question, schema_context, model, tokenizer):
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert SQLite SQL generation assistant.\n\n"
                "Your task is to convert the user's natural language question "
                "into exactly ONE valid SQLite SQL query.\n\n"
                "STRICT RULES:\n"
                "1. Return ONLY the SQL query. No explanations, comments, "
                "markdown, or multiple queries.\n"
                "2. Use ONLY tables and columns explicitly provided in the schema.\n"
                "3. Copy table and column names EXACTLY as they appear in the schema.\n"
                "4. NEVER invent a table or column name.\n"
                "5. Preserve underscores exactly; never replace them with spaces.\n"
                "6. Do not assume columns exist unless they appear in the schema.\n"
                "7. Use the simplest query that correctly answers the question.\n"
                "8. Use the minimum number of tables required.\n"
                "9. Do not add a JOIN unless the question requires another table.\n"
                "10. Use foreign-key relationships to construct JOIN conditions "
                "only when a JOIN is necessary.\n"
                "11. Use SQLite-compatible syntax only; do not use YEAR().\n"
                "12. For INTERSECT, UNION, and EXCEPT, use valid SQLite syntax "
                "without unnecessary parentheses around individual SELECT statements.\n"
                "13. Verify that every table and column exists in the schema.\n"
                "14. For aggregation, prefer the table that directly contains "
                "the requested attribute unless another table is necessary.\n"
                "15. Preserve the meaning of 'both', 'either', 'all', 'none', "
                "'only', and 'at least'.\n"
                "16. Avoid unnecessary JOINs, GROUP BY clauses, aliases, "
                "and subqueries.\n"
                "17. Select only requested columns, except those required for "
                "filtering, grouping, ordering, or constructing the result.\n"
                "18. Use COUNT(*) when counting records unless a specific "
                "column or distinct values must be counted.\n"
                "19. Translate conditions involving multiple values or categories "
                "without changing their logical meaning.\n"
                "20. Distinguish columns by meaning, not just similar names. "
                "For example, Song_Name is a song's name and Name may be a singer's name.\n"
                "21. Every alias referenced in SQL must be declared in FROM or JOIN.\n"
                "22. Before returning SQL, check table names, column names, "
                "JOIN necessity, WHERE conditions, aggregation, and SQLite syntax."
            )
        },
        {
            "role": "user",
            "content": f"Database schema:{schema_context}\n Question:{question}\n Generate the SQL query:"
        }
    ]

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(
        text,
        return_tensors="pt"
    ).to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=200,
            do_sample=False
        )

    generated_sql = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True
    )

    return generated_sql.strip()
