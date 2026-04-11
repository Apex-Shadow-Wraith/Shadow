"""Sample module with deliberate code issues for self-improvement testing.

This file is NOT production code. It exists solely as a test fixture
for SelfImprovementEngine's static analysis.
"""

# TODO: implement batch processing
# FIXME: this module needs proper error handling


def very_long_function(data):
    # No docstring — analyzer should flag this
    step_one = []
    for item in data:
        if isinstance(item, dict):
            step_one.append(item.get("value", 0))
        elif isinstance(item, (int, float)):
            step_one.append(item)
        else:
            step_one.append(0)

    step_two = []
    for val in step_one:
        if val > 100:
            step_two.append(val * 0.9)
        elif val > 50:
            step_two.append(val * 0.95)
        elif val > 10:
            step_two.append(val * 1.0)
        else:
            step_two.append(val * 1.1)

    step_three = {}
    for i, val in enumerate(step_two):
        bucket = "high" if val > 80 else "medium" if val > 30 else "low"
        if bucket not in step_three:
            step_three[bucket] = []
        step_three[bucket].append(val)

    totals = {}
    for bucket, values in step_three.items():
        total = 0
        count = 0
        for v in values:
            total += v
            count += 1
        if count > 0:
            totals[bucket] = {"sum": total, "avg": total / count, "count": count}
        else:
            totals[bucket] = {"sum": 0, "avg": 0, "count": 0}

    try:
        result = max(totals.items(), key=lambda x: x[1]["avg"])
    except:
        result = ("none", {"sum": 0, "avg": 0, "count": 0})

    try:
        summary = {
            "buckets": totals,
            "best_bucket": result[0],
            "best_avg": result[1]["avg"],
            "input_count": len(data),
            "processed_count": len(step_two),
        }
    except:
        summary = {"error": "processing failed"}

    return summary


def another_undocumented(x, y):
    # HACK: workaround for upstream bug
    return x + y


def clean_function(data: list[int]) -> int:
    """Sum all positive values."""
    return sum(x for x in data if x > 0)


class UndocumentedClass:
    def method_without_docs(self):
        return 42
