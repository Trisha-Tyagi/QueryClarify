
from pipeline import run_pipeline
from clarification import prepare_schema_context, detect_ambiguity
from sql_generator import clean_sql


MAX_CLARIFICATIONS = 2


def _build_resolved_question(original_question, clarification_history):
    """Combine the original question with clarification Q&A."""
    parts = [original_question.strip()]

    for item in clarification_history:
        parts.append(
            f"Clarification question: {item['question']}\n"
            f"User's answer: {item['answer']}"
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
        "db_id": db_id,
        "question": question,
        "predicted_sql": clean_sql(result["predicted_sql"]),
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
    """Start a query and request clarification if necessary."""

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
            clarification_question = (
                ambiguity["clarification_question"].strip()
            )

            if not clarification_question:
                clarification_question = (
                    "Could you specify what you want to see "
                    "in the query results?"
                )

            state = {
                "original_question": question,
                "db_id": db_id,
                "clarification_history": [],
                "pending_question": clarification_question,
                "top_k": top_k,
                "schema_context": schema_result["schema_context"],
                "selected_columns": schema_result["selected_columns"],
                "expanded_columns": schema_result["expanded_columns"]
            }

            return {
                "status": "clarification_required",
                "clarification_question": clarification_question,
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
    """Continue after the user answers a clarification question."""

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

    previous_question = state.get("pending_question")

    if not previous_question:
        return {
            "status": "error",
            "message": "No pending clarification question was found."
        }

    history = list(state.get("clarification_history", []))

    history.append({
        "question": previous_question,
        "answer": clarification_answer.strip()
    })

    if len(history) > MAX_CLARIFICATIONS:
        return {
            "status": "error",
            "message": "Maximum clarification limit reached."
        }

    resolved_question = _build_resolved_question(
        state["original_question"],
        history
    )

    try:
        # Do not run ambiguity detection again here.
        # Use Phase 6 to generate SQL from the resolved question.
        result = _run_phase6(
            question=resolved_question,
            db_id=state["db_id"],
            db=db,
            embedding_model=embedding_model,
            model=model,
            tokenizer=tokenizer,
            top_k=state.get("top_k", 5)
        )

        result["clarification_history"] = history
        result["original_question"] = state["original_question"]

        return result

    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc)
        }


import os
import json
import time
import sqlite3
from tqdm.auto import tqdm

from sql_generator import generate_sql, clean_sql
from schema_retrieval import hybrid_scores, select_columns
from schema_linking import expand_relationships
from sql_generator import create_schema_context


def evaluate_phase7(
    sample,
    schema_lookup,
    embedding_model,
    model,
    tokenizer,
    database_dir,
    save_path,
    top_k=5,
    checkpoint_every=10,
    limit=None
):
    """
    Evaluate Phase 7 on Spider examples.

    Clarification-required questions are recorded separately.
    SQL execution and result comparison use the Phase 6 method.

    This evaluation does not invent clarification answers.
    """

    if not isinstance(checkpoint_every, int) or checkpoint_every < 1:
        raise ValueError("checkpoint_every must be a positive integer.")

    save_dir = os.path.dirname(save_path)
    os.makedirs(save_dir or ".", exist_ok=True)

    if limit is not None:
        sample = sample[:limit]

    results = []

    # Resume from this Phase 7 evaluation's own checkpoint.
    if os.path.exists(save_path):
        with open(save_path, "r", encoding="utf-8") as f:
            results = json.load(f)

        completed_indices = {r["index"] for r in results}
        print(f"Resuming: {len(completed_indices)} records already saved.")
    else:
        completed_indices = set()
        print("Starting a fresh Phase 7 evaluation.")

    start_time = time.time()
    session_processed = 0

    with tqdm(
        total=len(sample),
        initial=len(completed_indices),
        desc="Phase 7 evaluation",
        unit="example"
    ) as progress:

        for i, example in enumerate(sample):

            if i in completed_indices:
                continue

            question = example["question"]
            db_id = example["db_id"]

            record = {
                "index": i,
                "db_id": db_id,
                "question": question,
                "gold_sql": example.get("query", ""),
                "status": None,
                "needs_clarification": None,
                "clarification_question": None,
                "clarification_reason": None,
                "predicted_sql": None,
                "execution_success": False,
                "result_match": False,
                "error": None
            }

            try:
                db = schema_lookup[db_id]

                # 1. Retrieve schema context for ambiguity detection.
                schema_result = prepare_schema_context(
                    question=question,
                    db=db,
                    embedding_model=embedding_model,
                    top_k=top_k
                )

                # 2. Detect ambiguity.
                ambiguity = detect_ambiguity(
                    question=question,
                    schema_context=schema_result["schema_context"],
                    model=model,
                    tokenizer=tokenizer
                )

                record["needs_clarification"] = (
                    ambiguity["needs_clarification"]
                )
                record["clarification_question"] = (
                    ambiguity["clarification_question"]
                )
                record["clarification_reason"] = ambiguity["reason"]

                # Do not fabricate answers to clarification requests.
                if ambiguity["needs_clarification"]:
                    record["status"] = "clarification_required"

                else:
                    # 3. Generate SQL using the same Phase 6 approach.
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

                    predicted_sql = clean_sql(
                        generate_sql(
                            question,
                            schema_context,
                            model,
                            tokenizer
                        )
                    )

                    record["predicted_sql"] = predicted_sql

                    # 4. Execute predicted and gold SQL using Phase 6 logic.
                    db_path = os.path.join(
                        database_dir,
                        db_id,
                        f"{db_id}.sqlite"
                    )

                    if not os.path.isfile(db_path):
                        raise FileNotFoundError(
                            f"Database file not found: {db_path}"
                        )

                    with sqlite3.connect(db_path, timeout=10) as conn:
                        predicted_result = conn.execute(
                            predicted_sql
                        ).fetchall()

                        gold_result = conn.execute(
                            example["query"]
                        ).fetchall()

                    record["execution_success"] = True

                    record["result_match"] = (
                        sorted(map(str, predicted_result))
                        == sorted(map(str, gold_result))
                    )

                    record["status"] = "completed"

            except Exception as exc:
                record["status"] = "error"
                record["error"] = str(exc)

            results.append(record)
            completed_indices.add(i)
            session_processed += 1

            # Save progress after every checkpoint interval.
            if session_processed % checkpoint_every == 0:
                results.sort(key=lambda r: r["index"])

                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(
                        results,
                        f,
                        indent=2,
                        ensure_ascii=False
                    )

            progress.update(1)

            clarification_count = sum(
                r["status"] == "clarification_required"
                for r in results
            )
            execution_count = sum(
                r["execution_success"]
                for r in results
            )
            match_count = sum(
                r["result_match"]
                for r in results
            )

            progress.set_postfix({
                "clarify": clarification_count,
                "executed": execution_count,
                "matches": match_count
            })

    # Final save.
    results.sort(key=lambda r: r["index"])

    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    total = len(results)
    clarification_count = sum(
        r["status"] == "clarification_required"
        for r in results
    )
    completed_count = sum(
        r["status"] == "completed"
        for r in results
    )
    error_count = sum(
        r["status"] == "error"
        for r in results
    )
    execution_successes = sum(
        r["execution_success"]
        for r in results
    )
    result_matches = sum(
        r["result_match"]
        for r in results
    )

    # SQL metrics use only examples that proceeded to SQL generation.
    attempted = completed_count

    print("\n========== PHASE 7 EVALUATION ==========")
    print("Records saved:", total)
    print("Clarification required:", clarification_count)
    print("SQL pipeline completed:", completed_count)
    print("Errors:", error_count)
    print("Execution successes:", execution_successes)
    print("Result matches:", result_matches)

    if attempted:
        print(
            f"Execution success among completed queries: "
            f"{execution_successes}/{attempted} "
            f"({execution_successes / attempted * 100:.2f}%)"
        )
        print(
            f"Result matches among completed queries: "
            f"{result_matches}/{attempted} "
            f"({result_matches / attempted * 100:.2f}%)"
        )

    print(
        f"Elapsed this session: "
        f"{(time.time() - start_time) / 60:.1f} minutes"
    )
    print("Saved to:", save_path)

    return results

