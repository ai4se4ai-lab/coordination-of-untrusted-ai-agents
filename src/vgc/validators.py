"""Finite policy language; other view checks establish only declared contracts."""
from itertools import product

STATES = ("open", "archived")
EVENTS = ("read", "put", "archive")


def reference(h, state, event):
    if event == "archive":
        return [200, "archived"]
    if h and state == "archived" and event == "put":
        return [409, "archived"]
    return [200, state]


def table(h):
    return [{"state": s, "event": e, "status": reference(h, s, e)[0],
             "next": reference(h, s, e)[1]} for s, e in product(STATES, EVENTS)]


def validate_table(h, rows):
    if not isinstance(rows, list) or len(rows) != 6:
        return False
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"state", "event", "status", "next"}:
            return False
        s, e = row["state"], row["event"]
        if not isinstance(s, str) or not isinstance(e, str):
            return False
        if s not in STATES or e not in EVENTS or (s, e) in seen:
            return False
        if type(row["status"]) is not int or type(row["next"]) is not str:
            return False
        if [row["status"], row["next"]] != reference(h, s, e):
            return False
        seen.add((s, e))
    return len(seen) == 6


def interpret(rows, events):
    state = "open"
    lookup = {(r["state"], r["event"]): (r["status"], r["next"]) for r in rows}
    trace = []
    for event in events:
        status, successor = lookup[state, event]
        trace.append((state, event, status, successor))
        state = successor
    return trace


def validate(stage, observation, value):
    if stage == "implementation":
        return validate_table(observation["source"]["strict"], value)
    if not isinstance(value, dict):
        return False
    if stage == "requirements":
        return type(value.get("strict")) is bool and value == {"clauses": ["R01", "R02", "R03"],
                         "strict": observation["source"]["strict"]}
    if stage == "architecture":
        return (set(value) == {"id_type", "operations"} and
                value["id_type"] in ("string", "integer") and
                value["operations"] == ["create", "read", "update", "archive", "list"])
    if stage == "verification":
        return (set(value) == {"id_type", "covered"} and
                value["id_type"] in ("string", "integer") and
                value["covered"] == ["R01", "R02", "R03"])
    if stage == "security":
        return value == {"assessed": ["create", "read", "update", "archive", "list"]}
    return False
