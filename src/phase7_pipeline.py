
from pipeline import run_pipeline
from clarification import (
    prepare_schema_context,
    detect_ambiguity
)


def _build_resolved_question(original_question, clarification_history):
    """Combine the original question with all clarification answers."""
    parts = [original_question.strip()]

    for item in clarification_history:
        parts.append(
            "Clarification question: " + item["question"]
            + "\nUser's answer: " + item["answer"]
        )

    return "\n\n".join(parts)


def _run_phase6(
    question,
    db_id,
    db,
    embedding_model,
    model,
    tokenizer,
    top_k
):
    """Run the existing Phase 6 pipeline without modifying it."""
    example = {
        "db_id": db_id,
        "question": question,
        "query": ""
    }

    result = run_pipeline(
        example=example,
        db=db,
        embedding_model=embedding_model,
        model=model,
        tokenizer=tokenizer,
        top_k=top_k
    )

    return {
        "status": "completed",
        "question": question,
        "predicted_sql": result["predicted_sql"],
        "schema_context": result["schema_context"],
        "selected_columns": result["selected_columns"],
        "expanded_columns": result["expanded_columns"],
        "pipeline_result": result
    }


def start_query(
    question,
    db_id,
    db,
    embedding_model,
    model,
    tokenizer,
    top_k=5
):
    """
    Start a new query.

    Returns either:
    - completed: SQL generated through Phase 6
    - clarification_required: question for the frontend
    - error: invalid input
    """
    if not isinstance(question, str) or not question.strip():
        return {
            "status": "error",
            "message": "Please enter a valid question."
        }

    question = question.strip()

    try:
        schema_result = prepare_schema_context(
            question=question,
            db=db,
            embedding_model=embedding_model,
            top_k=top_k
        )

        ambiguity = detect_ambiguity(
            question=question,
            schema_context=schema_result["schema_context"],
            model=model,
            tokenizer=tokenizer
        )

        if ambiguity["needs_clarification"]:
            state = {
                "original_question": question,
                "db_id": db_id,
                "clarification_history": [],
                "pending_question": ambiguity["clarification_question"],
                "top_k": top_k
            }

            return {
                "status": "clarification_required",
                "clarification_question": ambiguity[
                    "clarification_question"
                ],
                "reason": ambiguity["reason"],
                "state": state
            }

        return _run_phase6(
            question=question,
            db_id=db_id,
            db=db,
            embedding_model=embedding_model,
            model=model,
            tokenizer=tokenizer,
            top_k=top_k
        )

    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc)
        }


def continue_query(
    state,
    clarification_answer,
    db,
    embedding_model,
    model,
    tokenizer
):
    """
    Continue a query after receiving a frontend clarification answer.

    The returned state must be retained by the frontend if another
    clarification question is required.
    """
    if not isinstance(state, dict) or not state.get("original_question"):
        return {
            "status": "error",
            "message": "Invalid or missing clarification state."
        }

    if (
        not isinstance(clarification_answer, str)
        or not clarification_answer.strip()
    ):
        return {
            "status": "clarification_required",
            "clarification_question": (
                "Please provide an answer before continuing."
            ),
            "state": state
        }

    history = list(state.get("clarification_history", []))
    previous_question = state.get("pending_question")

    if not previous_question:
        return {
            "status": "error",
            "message": "No pending clarification question was found."
        }

    history.append({
        "question": previous_question,
        "answer": clarification_answer.strip()
    })

    resolved_question = _build_resolved_question(
        state["original_question"],
        history
    )

    top_k = state.get("top_k", 5)

    try:
        schema_result = prepare_schema_context(
            question=resolved_question,
            db=db,
            embedding_model=embedding_model,
            top_k=top_k
        )

        ambiguity = detect_ambiguity(
            question=resolved_question,
            schema_context=schema_result["schema_context"],
            model=model,
            tokenizer=tokenizer
        )

        if ambiguity["needs_clarification"]:
            updated_state = {
                **state,
                "clarification_history": history,
                "pending_question": ambiguity[
                    "clarification_question"
                ]
            }

            return {
                "status": "clarification_required",
                "clarification_question": ambiguity[
                    "clarification_question"
                ],
                "reason": ambiguity["reason"],
                "state": updated_state
            }

        return _run_phase6(
            question=resolved_question,
            db_id=state["db_id"],
            db=db,
            embedding_model=embedding_model,
            model=model,
            tokenizer=tokenizer,
            top_k=top_k
        )

    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc)
        }
