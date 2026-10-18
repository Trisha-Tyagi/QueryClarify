
import re
import torch
def create_schema_context(db, selected_columns, relationships=None):
    clean_tables = db["table_names"]
    original_tables = db["table_names_original"]
    clean_columns = db["column_names"]
    original_columns = db["column_names_original"]

    selected_set = set(selected_columns)
    schema_text = f"Database: {db['db_id']}\n\n"
    schema_text += "Relevant Tables and Columns:\n"

    for i, original_table in enumerate(original_tables):
        table_columns = []

        for j, original_col in enumerate(original_columns):
            table_idx, original_col_name = original_col

            if table_idx != i or original_col_name == "*":
                continue

            clean_col_name = clean_columns[j][1]
            clean_full_name = f"{clean_tables[i]}.{clean_col_name}"

            if clean_full_name in selected_set:
                table_columns.append(original_col_name)

        if table_columns:
            schema_text += f"\nTable: {original_table}\n"
            for col in table_columns:
                schema_text += f"- {col}\n"


    if relationships is None:
      relationships = []
      for fk1, fk2 in db["foreign_keys"]:
          table1_idx, col1 = original_columns[fk1]
          table2_idx, col2 = original_columns[fk2]

          clean_col1 = clean_columns[fk1][1]
          clean_col2 = clean_columns[fk2][1]

          clean_full1 = f"{clean_tables[table1_idx]}.{clean_col1}"
          clean_full2 = f"{clean_tables[table2_idx]}.{clean_col2}"

          if clean_full1 in selected_set and clean_full2 in selected_set:
              relationships.append(
                  f"{original_tables[table1_idx]}.{col1} = "
                  f"{original_tables[table2_idx]}.{col2}"
              )

    if relationships:
        schema_text += "\nForeign-Key Relationships:\n"
        for rel in relationships:
            schema_text += f"- {rel}\n"

    return schema_text



def clean_sql(sql):
    """Remove common formatting around a generated SQL query."""

    if not isinstance(sql, str):
        raise TypeError("SQL output must be a string")

    sql = sql.strip()

    # Remove Markdown code fences.
    sql = re.sub(
        r"^```(?:sqlite|sql)?\s*",
        "",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(r"\s*```$", "", sql)

    # Remove common SQL prefixes.
    sql = re.sub(
        r"^(?:SQL query|SQL)\s*:\s*",
        "",
        sql.strip(),
        flags=re.IGNORECASE,
    )

    return sql.strip()



def generate_sql(question, schema_context, model, tokenizer):

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert SQLite SQL generation assistant.\n\n"
                 "CRITICAL COUNTING RULE:\n"
                  "When asked how many records, people, singers, items, or rows exist, "
                  "you MUST use COUNT(*) unless the question explicitly asks to count "
                  "a particular column or distinct values. Do not substitute COUNT(id) "
                  "or COUNT(any_column) for COUNT(*).\n\n"
                "Your task is to convert the user's natural language question "
                "into exactly ONE valid SQLite SQL query.\n\n"

                "STRICT RULES:\n"

                "1. Return ONLY the SQL query. Do not provide explanations, "
                "comments, markdown, or multiple queries.\n"

                "2. Use ONLY the tables and columns explicitly provided in the schema.\n"

                "3. Copy table names and column names EXACTLY as they appear "
                "in the schema.\n"

                "4. NEVER invent a table or column name.\n"

                "5. NEVER change an identifier. If a column contains an underscore, "
                "keep the underscore exactly.\n"

                "6. Do NOT replace underscores with spaces. For example, "
                "`song_name` must remain `song_name`, not `song name`.\n"

                "7. Do NOT assume that a table has a column such as `id`, `pet_id`, "
                "`pet_type`, etc. unless that exact column is present in the schema.\n"

                "8. Use the simplest SQL query that correctly answers the question.\n"

                "9. Use the minimum number of tables required to answer the question. "
                "Do NOT add a JOIN merely because a foreign-key relationship is provided.\n"

                "10. Before adding a JOIN, check whether the question actually requires "
                "information, filtering, grouping, or conditions from the other table. "
                "If the question can be answered using one table, use only that table.\n"

                "11. Foreign-key relationships are provided only to help you construct "
                "JOIN conditions when a JOIN is genuinely necessary. "
                "They do NOT imply that the related table must be included.\n"

                "12. Use SQLite-compatible SQL syntax only.\n"

                "13. Do NOT use unsupported functions such as YEAR(). "
                "Use SQLite-compatible expressions instead.\n"

                "14. For INTERSECT, UNION, or EXCEPT, write valid SQLite syntax "
                "and avoid unnecessary parentheses around individual SELECT statements.\n"

                "15. Before returning the SQL, verify that every table name and "
                "every column name exists in the provided schema.\n"

                "16. For aggregation questions, use the table that directly contains "
                "the requested attribute whenever possible. Do not introduce another "
                "table unless it is required for filtering, grouping, or obtaining "
                "information that is not available in the selected table.\n"

                "17. Do not add a JOIN simply because two tables are related. "
                "If a question asks for COUNT, MIN, MAX, AVG, SUM, or another "
                "aggregate that can be answered from one table, prefer that "
                "single-table query.\n"

                "18. Carefully preserve the logical meaning of words such as "
                "'both', 'either', 'all', 'none', 'only', and 'at least'. "
                "Do not replace a condition requiring multiple independent criteria "
                "with a logically different condition such as BETWEEN.\n"

                "19. Prefer the simplest query that directly matches the wording "
                "of the question. Avoid unnecessary JOINs, GROUP BY clauses, "
                "aliases, or subqueries.\n"

                "20. Do not select columns that are not requested by the question "
                "unless they are required for filtering, grouping, ordering, "
                "or constructing the result.\n"

                "21. When the question asks for information from only one table, "
                "do not join another table even if a foreign-key relationship exists.\n"

                "22. When a JOIN is necessary, use the provided foreign-key "
                "relationship to construct the correct JOIN condition.\n"

                "23. For counting records, use COUNT(*) when the question asks "
                "for the number of records and no specific column needs to be counted. "
                "Use COUNT(column) or COUNT(DISTINCT column) only when the question "
                "requires it.\n"

                "24. For conditions involving multiple values or categories, "
                "translate the natural-language logic exactly. Do not simplify "
                "the condition unless the simplified expression is logically equivalent.\n"

                "25. Before returning the final SQL, mentally verify:\n"
                "    - every table exists in the schema,\n"
                "    - every column exists in the schema,\n"
                "    - every JOIN is necessary,\n"
                "    - the WHERE conditions match the question,\n"
                "    - the aggregation matches the question,\n"
                "    - the SQL is valid SQLite syntax.\n"


                "26. Distinguish columns by meaning, not just similar names. "
                "For example, use Song_Name for a song's name and Name for a singer's name.\n"

                "27. Every alias referenced in SQL must be declared in FROM or JOIN.\n"


            )
        },
        {
            "role": "user",
            "content": f"""Database schema:{schema_context}\nQuestion:{question}\nGenerate the SQL query:"""
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

    return clean_sql(generated_sql)