import json
from ..validators import table


def valid_proposal(request, id_type="string"):
    o = json.loads(request.observation)
    stage = o["stage"]
    if stage == "requirements":
        return {"clauses": ["R01", "R02", "R03"], "strict": o["source"]["strict"]}
    if stage == "architecture":
        return {"id_type": id_type, "operations": ["create", "read", "update", "archive", "list"]}
    if stage == "implementation":
        return table(o["source"]["strict"])
    if stage == "verification":
        return {"id_type": id_type, "covered": ["R01", "R02", "R03"]}
    if stage == "security":
        return {"assessed": ["create", "read", "update", "archive", "list"]}
    raise ValueError(stage)
