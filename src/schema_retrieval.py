
import re

import nltk
from nltk import pos_tag
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords, wordnet
from sentence_transformers import util


# NLTK data is optional. Some environments cannot download its corpora/taggers;
# in that case use lightweight built-in tokenization and stop words.
_FALLBACK_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "show", "that", "the",
    "their", "this", "to", "what", "which", "who", "with",
}
lemmatizer = WordNetLemmatizer()
try:
    stop_words = set(stopwords.words("english"))
    for resource in (
        "corpora/wordnet", "taggers/averaged_perceptron_tagger_eng",
        "tokenizers/punkt", "tokenizers/punkt_tab",
    ):
        nltk.data.find(resource)
    _NLTK_RESOURCES_AVAILABLE = True
except LookupError:
    stop_words = _FALLBACK_STOP_WORDS
    _NLTK_RESOURCES_AVAILABLE = False


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
    if _NLTK_RESOURCES_AVAILABLE:
        tokens = nltk.word_tokenize(question)
        tagged_tokens = pos_tag(tokens)
        normalized_words = [
            lemmatizer.lemmatize(word, get_wordnet_pos(tag))
            for word, tag in tagged_tokens
            if word.isalpha()
        ]
        return [word for word in normalized_words if word not in stop_words]

    tokens = re.findall(r"[a-z]+", question)
    normalized_words = []
    for word in tokens:
        if len(word) > 4 and word.endswith("ies"):
            word = word[:-3] + "y"
        elif len(word) > 4 and word.endswith("ing"):
            word = word[:-3]
        elif len(word) > 3 and word.endswith("ed"):
            word = word[:-2]
        elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        if word not in stop_words:
            normalized_words.append(word)
    return normalized_words


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
    """
    Select the highest-scoring columns while preserving
    useful lexical matches from already-selected tables.
    """

    if not hybrid_results:
        return []

    # Rank all columns by their hybrid score.
    ranked_results = sorted(
        hybrid_results,
        key=lambda item: item[3],
        reverse=True
    )

    # Select the top-ranked columns.
    selected_columns = [
        column
        for column, lexical, semantic, hybrid
        in ranked_results[:top_k]
    ]

    # Identify tables represented in the initial selection.
    selected_tables = {
        column.split(".", 1)[0]
        for column in selected_columns
    }

    # Add lexically relevant columns from those same tables.
    # Limit additions to avoid sending the entire schema to the LLM.
    max_extra_columns = 10
    extra_count = 0

    for column, lexical, semantic, hybrid in ranked_results[top_k:]:
        table = column.split(".", 1)[0]

        if (
            table in selected_tables
            and lexical > 0
            and column not in selected_columns
        ):
            selected_columns.append(column)
            extra_count += 1

        if extra_count >= max_extra_columns:
            break

    return selected_columns

