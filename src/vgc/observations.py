"""Exact, typed JSON observations. Digests are never admission keys."""
import json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def selected(context, document):
    # Re-evaluate membership, including a newly matching finding and empty sets.
    return {k: v for k, v in sorted(context.items()) if v["document"] == document}
