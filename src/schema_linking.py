
def expand_related_tables(db, selected_tables):
    expanded_tables = set(selected_tables)

    for fk in db["foreign_keys"]:
        col1 = db["column_names"][fk[0]]
        col2 = db["column_names"][fk[1]]

        table1 = db["table_names"][col1[0]]
        table2 = db["table_names"][col2[0]]

        if table1 in selected_tables:
            expanded_tables.add(table2)

        if table2 in selected_tables:
            expanded_tables.add(table1)

    return list(expanded_tables)

def expand_relationships(db, selected_columns):

    expanded_columns = set(selected_columns)
    relationships = []

    selected_tables = {
        column.split(".", 1)[0]
        for column in selected_columns
    }

    # Only expand relationships when more than one table
    # is already relevant to the question.
    if len(selected_tables) <= 1:
        return sorted(expanded_columns), relationships

    for fk in db["foreign_keys"]:

        # Normalized names - used for checking selected tables
        col1 = db["column_names"][fk[0]]
        col2 = db["column_names"][fk[1]]

        table1 = db["table_names"][col1[0]]
        table2 = db["table_names"][col2[0]]

        full_col1 = f"{table1}.{col1[1]}"
        full_col2 = f"{table2}.{col2[1]}"

        if table1 in selected_tables or table2 in selected_tables:

            # Add normalized columns for the retrieval pipeline
            expanded_columns.add(full_col1)
            expanded_columns.add(full_col2)

            # Original database identifiers for SQL generation
            original_col1 = db["column_names_original"][fk[0]]
            original_col2 = db["column_names_original"][fk[1]]

            original_table1 = db["table_names_original"][original_col1[0]]
            original_table2 = db["table_names_original"][original_col2[0]]

            relationship = (
                f"{original_table1}.{original_col1[1]} = "
                f"{original_table2}.{original_col2[1]}"
            )

            relationships.append(relationship)

    return sorted(expanded_columns), relationships


def get_relevant_relationships(db, selected_columns):

    selected_set = set(selected_columns)
    relationships = []

    for fk in db["foreign_keys"]:

        col1 = db["column_names"][fk[0]]
        col2 = db["column_names"][fk[1]]

        table1 = db["table_names"][col1[0]]
        table2 = db["table_names"][col2[0]]

        full_col1 = f"{table1}.{col1[1]}"
        full_col2 = f"{table2}.{col2[1]}"

        if full_col1 in selected_set and full_col2 in selected_set:
            relationships.append(
                f"{full_col1} → {full_col2}"
            )

    return relationships
