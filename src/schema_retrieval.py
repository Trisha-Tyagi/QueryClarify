
import nltk
from nltk import pos_tag
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords, wordnet
from sentence_transformers import util


# Initialize text-processing resources
lemmatizer = WordNetLemmatizer()
stop_words = set(stopwords.words("english"))


def get_wordnet_pos(tag):
    if tag.startswith("J"):
        return wordnet.ADJ
    elif tag.startswith("V"):
        return wordnet.VERB
    elif tag.startswith("N"):
        return wordnet.NOUN
    elif tag.startswith("R"):
        return wordnet.ADV
    else:
        return wordnet.NOUN


def preprocess_question(question):
    question = question.lower()
    tokens = nltk.word_tokenize(question)
    tagged_tokens = pos_tag(tokens)

    normalized_words = [
        lemmatizer.lemmatize(word, get_wordnet_pos(tag))
        for word, tag in tagged_tokens
        if word.isalpha()
    ]

    filtered_words = [
        word for word in normalized_words
        if word not in stop_words
    ]

    return filtered_words


def lexical_scores(question, db):
    question_terms = set(preprocess_question(question))
    results = []

    for i, table in enumerate(db["table_names"]):
        for column in db["column_names"]:
            if column[0] != i:
                continue

            column_name = column[1]

            if column_name == "*":
                continue

            full_name = f"{table}.{column_name}"

            schema_words = preprocess_question(column_name)
            schema_words += preprocess_question(table)
            schema_terms = set(schema_words)

            overlap = question_terms.intersection(schema_terms)
            score = len(overlap) / max(len(schema_terms), 1)

            results.append((full_name, score))

    return results


def semantic_scores(question, db, embedding_model):
    schema_items = []

    for i, table in enumerate(db["table_names"]):
        for column in db["column_names"]:
            if column[0] == i and column[1] != "*":
                schema_items.append(f"{table}.{column[1]}")

    if not schema_items:
        return []

    question_embedding = embedding_model.encode(
        question,
        convert_to_tensor=True
    )

    schema_embeddings = embedding_model.encode(
        schema_items,
        convert_to_tensor=True
    )

    scores = util.cos_sim(
        question_embedding,
        schema_embeddings
    )[0]

    return list(zip(schema_items, scores.cpu().tolist()))


def hybrid_scores(question, db, embedding_model, alpha=0.4):
    lexical_results = dict(lexical_scores(question, db))
    semantic_results = dict(
        semantic_scores(question, db, embedding_model)
    )

    results = []

    for column, semantic in semantic_results.items():
        lexical = lexical_results.get(column, 0.0)

        hybrid = (
            alpha * lexical
            + (1 - alpha) * semantic
        )

        results.append((
            column,
            lexical,
            semantic,
            hybrid
        ))

    results.sort(key=lambda x: x[3], reverse=True)

    return results


def select_columns(hybrid_results, top_k=5):
    selected_columns = [
        column
        for column, lexical, semantic, hybrid
        in hybrid_results[:top_k]
    ]

    selected_tables = {
        column.split(".", 1)[0]
        for column in selected_columns
    }

    for column, lexical, semantic, hybrid in hybrid_results:
        table = column.split(".", 1)[0]

        if table in selected_tables and lexical > 0:
            if column not in selected_columns:
                selected_columns.append(column)

    return selected_columns
