import json
from pathlib import Path
from statistics import mean

from app.rag import semantic_search


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_EVAL_FILE = (
    "evaluation/rag_test_cases.json"
)


# ============================================================
# LOAD EVALUATION DATASET
# ============================================================

def load_eval_cases(
    file_path: str = DEFAULT_EVAL_FILE,
) -> list[dict]:

    path = Path(
        file_path
    )

    if not path.exists():

        raise FileNotFoundError(
            f"Evaluation file not found: {path}"
        )


    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(
            file
        )


    if not isinstance(
        data,
        list,
    ):

        raise ValueError(
            "Evaluation dataset must "
            "contain a JSON list."
        )


    return data


# ============================================================
# EVALUATE ONE QUERY
# ============================================================

def evaluate_case(
    case: dict,
    limit: int = 3,
) -> dict:

    query = case[
        "query"
    ]

    expected_file = case[
        "expected_file"
    ]


    print(
        f"\n[EVAL] Query: {query}"
    )

    print(
        f"[EVAL] Expected: {expected_file}"
    )


    result = semantic_search(
        query=query,
        limit=limit,
    )


    if not result.get(
        "success"
    ):

        return {
            "query":
                query,

            "expected_file":
                expected_file,

            "success":
                False,

            "error":
                result.get(
                    "error"
                ),

            "hit_at_1":
                0,

            "hit_at_k":
                0,

            "reciprocal_rank":
                0.0,
        }


    results = result.get(
        "results",
        [],
    )


    retrieved_files = [
        item.get(
            "filename"
        )
        for item in results
    ]


    print(
        "[EVAL] Retrieved:",
        retrieved_files,
    )


    # ========================================================
    # HIT@1
    # ========================================================

    hit_at_1 = 0

    if (
        retrieved_files
        and
        retrieved_files[0]
        == expected_file
    ):

        hit_at_1 = 1


    # ========================================================
    # HIT@K
    # ========================================================

    hit_at_k = (
        1
        if expected_file
        in retrieved_files
        else 0
    )


    # ========================================================
    # RECIPROCAL RANK
    # ========================================================

    reciprocal_rank = 0.0


    for rank, filename in enumerate(
        retrieved_files,
        start=1,
    ):

        if filename == expected_file:

            reciprocal_rank = (
                1.0
                / rank
            )

            break


    return {

        "query":
            query,

        "expected_file":
            expected_file,

        "retrieved_files":
            retrieved_files,

        "success":
            True,

        "hit_at_1":
            hit_at_1,

        "hit_at_k":
            hit_at_k,

        "reciprocal_rank":
            reciprocal_rank,

        "results":
            [
                {
                    "filename":
                        item.get(
                            "filename"
                        ),

                    "similarity":
                        item.get(
                            "similarity"
                        ),

                    "chunk_index":
                        item.get(
                            "chunk_index"
                        ),
                }

                for item in results
            ],
    }


# ============================================================
# RUN COMPLETE RAG EVALUATION
# ============================================================

def evaluate_rag(
    file_path: str = DEFAULT_EVAL_FILE,
    limit: int = 3,
) -> dict:

    cases = load_eval_cases(
        file_path
    )


    print(
        f"\n[EVAL] Running "
        f"{len(cases)} RAG test cases"
    )


    case_results = []


    for case in cases:

        result = evaluate_case(
            case=case,
            limit=limit,
        )

        case_results.append(
            result
        )


    # ========================================================
    # METRICS
    # ========================================================

    hit_at_1_values = [
        result[
            "hit_at_1"
        ]
        for result in case_results
    ]


    hit_at_k_values = [
        result[
            "hit_at_k"
        ]
        for result in case_results
    ]


    reciprocal_ranks = [
        result[
            "reciprocal_rank"
        ]
        for result in case_results
    ]


    total_cases = len(
        case_results
    )


    hit_at_1 = (
        mean(
            hit_at_1_values
        )
        if hit_at_1_values
        else 0.0
    )


    hit_at_k = (
        mean(
            hit_at_k_values
        )
        if hit_at_k_values
        else 0.0
    )


    mrr = (
        mean(
            reciprocal_ranks
        )
        if reciprocal_ranks
        else 0.0
    )


    summary = {

        "total_cases":
            total_cases,

        "hit_at_1":
            hit_at_1,

        f"hit_at_{limit}":
            hit_at_k,

        "mean_reciprocal_rank":
            mrr,

        "cases":
            case_results,
    }


    print(
        "\n================================="
    )

    print(
        "RAG EVALUATION SUMMARY"
    )

    print(
        "================================="
    )

    print(
        f"Cases: {total_cases}"
    )

    print(
        f"Hit@1: {hit_at_1:.3f}"
    )

    print(
        f"Hit@{limit}: {hit_at_k:.3f}"
    )

    print(
        f"MRR: {mrr:.3f}"
    )


    return summary