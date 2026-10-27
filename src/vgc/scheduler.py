from .providers.scripted import valid_proposal


def repair(controller):
    """Topological frozen-input pass; classify failure instead of spinning."""
    while True:
        eligible = [key for key in sorted(controller.active)
                    if not controller._usable(key) and not controller.records[key].failed
                    and controller.records[key].attempts < controller.budget
                    and not any(p.job == key for p in controller.pending.values())]
        if not eligible:
            break
        for key in eligible:
            identity = controller.dispatch(key)
            if identity is not None:
                controller.resolve(identity, valid_proposal(controller.pending[identity]))
    return controller.check_publication()["ok"]
