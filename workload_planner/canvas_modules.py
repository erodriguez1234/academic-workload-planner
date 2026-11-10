"""Read module membership separately from assignments; never infer calendar weeks."""

from dataclasses import dataclass
from urllib.parse import urlsplit

from workload_planner.canvas_client import CanvasClient, CanvasClientError
from workload_planner.canvas_import import ImportedAssignment


@dataclass(frozen=True)
class ModulePlacement:
    key: str
    course: str
    name: str
    assignment_ids: tuple[str, ...]


@dataclass(frozen=True)
class ModuleCatalog:
    modules: tuple[ModulePlacement, ...]
    warnings: tuple[str, ...]


def load_module_catalog(client: CanvasClient, courses: list[dict], items: tuple[ImportedAssignment, ...] | list[ImportedAssignment], site: str) -> ModuleCatalog:
    modules, warnings, seen = [], [], set()
    for course in courses:
        cid = course["id"]
        prefix = f"canvas:{urlsplit(site).netloc.lower()}:{cid}:"
        lookup = {}
        for item in items:
            aid = item.assignment.assignment_id
            if aid.startswith(prefix):
                lookup[("Assignment", int(aid.rsplit(":", 1)[-1]))] = aid
                if item.quiz_id:
                    lookup[("Quiz", item.quiz_id)] = aid
                if item.discussion_id:
                    lookup[("Discussion", item.discussion_id)] = aid
        try:
            records = client.list_modules(cid)
        except CanvasClientError as error:
            warnings.append(f"Module placement unavailable for course {cid}: {error}")
            continue
        for record in records:
            mid, name = record.get("id"), record.get("name")
            if type(mid) is not int or mid <= 0 or not isinstance(name, str) or not name.strip() or (cid, mid) in seen:
                warnings.append(f"Course {cid}: invalid/duplicate module metadata; placement is incomplete.")
                continue
            seen.add((cid, mid))
            try:
                entries = client.list_module_items(cid, mid)
            except CanvasClientError as error:
                warnings.append(f"Could not inspect course {cid}, module {mid}: {error}")
                continue
            assigned = []
            for entry in entries:
                kind, content = entry.get("type"), entry.get("content_id")
                if kind not in ("Assignment", "Quiz", "Discussion"):
                    continue
                if type(content) is not int or content <= 0:
                    warnings.append(f"Course {cid}, module {mid}: invalid content ID; placement is incomplete.")
                    continue
                aid = lookup.get((kind, content))
                if aid and aid not in assigned:
                    assigned.append(aid)
                elif not aid and kind in ("Quiz", "Discussion"):
                    warnings.append(f"Course {cid}, module {mid}: a {kind.lower()} could not be linked reliably to an imported assignment. Set its planning week manually if needed.")
            modules.append(ModulePlacement(f"{prefix}module:{mid}", course["name"], name, tuple(assigned)))
    return ModuleCatalog(tuple(modules), tuple(warnings))
