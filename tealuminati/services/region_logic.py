def update_counters(counters: dict[str, int], added: set[str], removed: set[str]) -> None:
    for nation in added:
        current = counters.get(nation)
        if current is not None and current < 0:
            del counters[nation]
            continue
        counters[nation] = (current or 0) + 1

    for nation in removed:
        current = counters.get(nation)
        if current is not None and current > 0:
            del counters[nation]
            continue
        counters[nation] = (current or 0) - 1

    for nation in list(counters):
        if nation in added or nation in removed:
            continue
        current = counters[nation]
        remaining = current - 1 if current > 0 else current + 1
        if remaining == 0:
            del counters[nation]
        else:
            counters[nation] = remaining


def confirm_changes(
    counters: dict[str, int], join_threshold: int, leave_threshold: int
) -> tuple[set[str], set[str]]:
    joins = {n for n, c in counters.items() if c >= join_threshold}
    leaves = {n for n, c in counters.items() if c <= -leave_threshold}
    return joins, leaves


def can_notify(last_notified: float | None, now: float, cooldown: int) -> bool:
    return last_notified is None or (now - last_notified) > cooldown
