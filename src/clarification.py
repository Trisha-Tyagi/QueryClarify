
import json
import re
import torch
from schema_retrieval import hybrid_scores, select_columns
from schema_linking import expand_relationships
from sql_generator import create_schema_context

def prepare_schema_context(question, db, embedding_model, top_k=5):
    """
    Retrieve relevant columns and prepare schema context
    for ambiguity detection.
    """

    hybrid_results = hybrid_scores(
        question,
        db,
        embedding_model
    )

    selected_columns = select_columns(
        hybrid_results,
        top_k=top_k
    )

    expanded_columns, relationships = expand_relationships(
        db,
        selected_columns
    )

    schema_context = create_schema_context(
        db,
        expanded_columns,
        relationships
    )

    return {
        "schema_context": schema_context,
        "selected_columns": selected_columns,
        "expanded_columns": expanded_columns,
        "relationships": relationships
    }



def detect_ambiguity(question, schema_context, model, tokenizer):

    system_prompt = """
    You are a careful ambiguity detector for a Text-to-SQL system.

    Your task is to decide whether a user question genuinely needs
    clarification before SQL can be generated.

    IMPORTANT RULES:

    1. Set needs_clarification to TRUE only when the question has
      at least two reasonable interpretations that would produce
      materially different SQL queries.

    2. Do NOT ask clarification questions just because the user
      uses informal wording, plural nouns, or a synonym for a
      table name. Use the provided schema to identify tables
      and columns.

    3. Do NOT ask which columns the user wants if the requested
      information is already stated or reasonably implied.

    4. Treat common database language as clear:
      - "youngest singer" means the singer with the minimum age.
      - "oldest singer" means the singer with the maximum age.
      - "descending order of age" means age from highest to lowest.
      - "different countries" means distinct countries.
      - "singers above age 20" means singers whose age is greater
        than 20.

    5. Do NOT invent ambiguity. If a reasonable interpretation
      is clear from the question and schema, set
      needs_clarification to FALSE.

    6. Ask for clarification when essential information is missing
      or two plausible interpretations would lead to materially
      different results. For example, "Show me the details" may
      not specify which entity or information is wanted.

    7. Do not confuse a difficult SQL query with an ambiguous
      question. If the question is clear but complex, do not
      request clarification.

    OUTPUT REQUIREMENTS:

    Return ONLY one valid JSON object with exactly these keys:
    - "needs_clarification": a JSON boolean
    - "reason": a string
    - "clarification_question": a string

    If clarification is NOT needed:
    - needs_clarification must be false
    - reason must be an empty string
    - clarification_question must be an empty string

    If clarification IS needed:
    - needs_clarification must be true
    - reason must briefly explain the genuine ambiguity
    - clarification_question must contain one concise question
      that resolves that ambiguity

    Never return missing keys, null values, or text outside the JSON.
    """

    user_prompt = (
        "Relevant database schema:\n"
        + str(schema_context)
        + "\n\nUser's question:\n"
        + str(question)
        + "\n\nIs clarification genuinely necessary before generating SQL? "
        "Return JSON only."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(prompt, return_tensors="pt")
    inputs = inputs.to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=160,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )

    generated_tokens = outputs[0][inputs["input_ids"].shape[-1]:]
    response = tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True
    ).strip()
    print("RAW AMBIGUITY DETECTOR RESPONSE:", repr(response))

    match = re.search(r"\{.*\}", response, re.DOTALL)

    if not match:
        raise ValueError(
            "Invalid JSON from ambiguity detector: " + response
        )

    try:
        result = json.loads(match.group())
        
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Could not parse detector response: " + response
        ) from exc


    
    value = result.get("needs_clarification")

    if isinstance(value, str):
        if value.strip().lower() == "true":
            result["needs_clarification"] = True
        elif value.strip().lower() == "false":
            result["needs_clarification"] = False
        else:
            raise ValueError(
                "Unexpected needs_clarification value: " + repr(value)
            )

    elif not isinstance(value, bool):
        raise ValueError(
            "Unexpected needs_clarification type: " + str(type(value))
        )


        # Validate the reason.
    reason = result.get("reason", "")

    if not isinstance(reason, str):
        reason = str(reason) if reason is not None else ""

    # Validate the clarification question according to the decision.
    clarification_question = result.get("clarification_question", "")

    if result["needs_clarification"]:
        if not isinstance(clarification_question, str):
            clarification_question = ""

        if not clarification_question.strip():
            raise ValueError(
                "Clarification is required, but the detector "
                "did not provide a valid clarification question."
            )
    else:
        # A clear question does not need a clarification question.
        reason = ""
        clarification_question = ""
    return {
        "needs_clarification": result["needs_clarification"],
        "reason": reason,
        "clarification_question": clarification_question
    }



def resolve_question(original_question, clarification_answer):
    original_question = original_question.strip()
    clarification_answer = clarification_answer.strip()

    if not original_question:
        raise ValueError("Original question cannot be empty.")

    if not clarification_answer:
        raise ValueError("Clarification answer cannot be empty.")

    return (
        original_question
        + "\nClarification provided by the user: "
        + clarification_answer
    )



def validate_clarification_answer(answer, db):
    answer_lower = answer.lower().strip()

    available_columns = sorted(set(
        column[1].lower().replace("_", " ")
        for column in db["column_names"]
        if column[0] >= 0
    ))

    # Exact column-name match
    if answer_lower in available_columns:
        return {
            "valid": True,
            "matched_columns": [answer_lower],
            "message": ""
        }

    return {
        "valid": False,
        "matched_columns": [],
        "message": (
            f"The requested criterion '{answer}' could not be "
            "matched exactly to a column in the database schema."
        )
    }


def ask_clarification(clarification_question):
    """
    Ask the user for clarification and collect their answer.
    Intended for interactive Colab testing.
    """
    if not clarification_question or not clarification_question.strip():
        raise ValueError("Clarification question cannot be empty.")

    print("\nQueryClarify AI:", clarification_question)

    answer = input("Your answer: ").strip()

    if not answer:
        return {
            "answered": False,
            "answer": "",
            "message": "Clarification answer cannot be empty."
        }

    return {
        "answered": True,
        "answer": answer,
        "message": ""
    }

def collect_valid_clarification_answer(clarification_question, db):
    """
    Ask repeatedly until the user provides a schema-matching answer.
    """
    while True:
        response = ask_clarification(clarification_question)

        if not response["answered"]:
            print(response["message"])
            continue

        validation = validate_clarification_answer(
            response["answer"],
            db
        )

        if validation["valid"]:
            return response["answer"]

        print("\nQueryClarify AI:", validation["message"])
        print("Please try again with a criterion available in the database.")

