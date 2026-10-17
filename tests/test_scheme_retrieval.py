import sys
sys.path.insert(0, "/content/QueryClarify/src")

from schema_retrieval import preprocess_question

result = preprocess_question(
    "Which students were studying in the departments?"
)

print(result)
