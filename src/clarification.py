
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

    system_prompt = (
        "You are an ambiguity detector for a Text-to-SQL system. "
        "Determine whether the user's question has multiple materially "
        "different interpretations that would produce different SQL queries. "
        "Do not clarify questions that are sufficiently clear. "
        "Do not assume a column is missing just because it is absent from "
        "the provided schema context. Ask only one concise question when "
        "necessary. Return ONLY valid JSON with exactly these keys: "
        '"needs_clarification" (boolean), "reason" (string), '
        'and "clarification_question" (string). '
        "If clarification is unnecessary, use false and empty strings."
    )

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


    if not isinstance(result.get("reason"), str):
        raise ValueError("Invalid reason value.")

    if not isinstance(result.get("clarification_question"), str):
        raise ValueError("Invalid clarification_question value.")

    if result["needs_clarification"]:
        if not result["clarification_question"].strip():
            raise ValueError("Clarification question is missing.")
    else:
        result["reason"] = ""
        result["clarification_question"] = ""

    return {
        "needs_clarification": result["needs_clarification"],
        "reason": result["reason"],
        "clarification_question": result["clarification_question"]
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

