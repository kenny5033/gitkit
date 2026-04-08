from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from typing import List, Optional, Set
import uuid
from git import GitCommandError, TagReference
from gitkit.utils import get_app_repo


class DataNodeType(int, Enum):
    SERIES = 0
    CONTEXT = 1


@dataclass
class DataNode:
    type: DataNodeType
    dependent_on: List[str] = field(default_factory=list)


class PartType(int, Enum):
    PART = 0
    CONTEXT = 1
    OTHER = 2  # not gitkit


def interpret_part_type(*, part_name: Optional[str] = None) -> PartType:
    from gitkit.logic.parts import is_part_name_valid

    repo = get_app_repo()

    if part_name is None:
        part_name = repo.head.reference.name

    if is_part_name_valid(part_name):
        return PartType.PART

    if part_name in repo.tags:
        return PartType.CONTEXT

    return PartType.OTHER


def load_data_node(*, part_name: Optional[str] = None) -> DataNode | None:
    repo = get_app_repo()

    if part_name is None:
        part_name = repo.head.reference.name

    part_type = interpret_part_type(part_name=part_name)

    if part_type == PartType.PART:
        from gitkit.logic.parts import parse_part_name

        series_name, _ = parse_part_name(part_name)
        return DataNode(**json.loads(repo.tags[series_tag(series_name)].commit.message))

    if part_type == PartType.CONTEXT:
        return DataNode(**json.loads(repo.tags[part_name].commit.message))

    return None


def save_data_node(node: DataNode, tag_name: str) -> TagReference:
    repo = get_app_repo()

    old_head = repo.head.reference
    node_head = repo.create_head(tag_name)
    node_head.checkout()

    info = asdict(node)
    repo.git.commit("--allow-empty", "-m", json.dumps(info))
    node_tag = repo.create_tag(tag_name, force=True)

    old_head.checkout()
    repo.delete_head(node_head, force=True)

    return node_tag


def series_tag(name: str) -> str:
    return f"(gk){name}-series-info"


def context_tag(name: str) -> str:
    return f"(gk){name}"


def start_series(name: str, *, exists_ok: bool = False, force: bool = False):
    from gitkit.logic.parts import make_part

    repo = get_app_repo()

    if (already_exists := series_exists(name)) and exists_ok:
        return

    if not force and already_exists:
        raise ValueError(f"Series {name} already exists")

    series_info = DataNode(type=DataNodeType.SERIES)

    # if it is a gitkit head, mark it as a series dependency
    # else if it is a context commit, use its dependencies
    current_part_type = interpret_part_type()
    if current_part_type == PartType.PART:
        series_info.dependent_on = [repo.head.reference.name]
    elif current_part_type == PartType.CONTEXT:
        context_info = load_data_node()
        if context_info is None:
            raise ValueError("Could not find data node for this context")
        series_info.dependent_on = context_info.dependent_on

    save_data_node(series_info, series_tag(name))

    make_part(1.0, on_series=name)


def series_exists(name: str) -> bool:
    repo = get_app_repo()
    return series_tag(name) in [tag.name for tag in repo.tags]


def create_context(other_part_name: str, *, name: Optional[str] = None) -> DataNode:
    repo = get_app_repo()

    def get_dependencies(part_name: str) -> List[str]:
        part_type = interpret_part_type(part_name=part_name)
        if part_type == PartType.OTHER:
            raise ValueError(
                "Cannot make context where the base is not a gitkit managed head. Try making a series instead."
            )

        if part_type == PartType.PART:
            return [part_name]
        elif part_type == PartType.CONTEXT:
            node = load_data_node(part_name=part_name)
            if node is None:
                raise ValueError(f"Cannot find data node for context {part_name}")
            return node.dependent_on

        return []

    base_part_name = repo.head.reference.name

    base_dependencies = get_dependencies(base_part_name)
    other_dependencies = get_dependencies(other_part_name)

    context_info = DataNode(
        type=DataNodeType.CONTEXT, dependent_on=base_dependencies + other_dependencies
    )

    if name is None:
        name = str(uuid.uuid4())

    save_data_node(context_info, context_tag(name))

    context_head = repo.create_head(name)
    context_head.checkout()

    try:
        repo.git.merge(
            other_part_name,
            m=f"(gitkit) context merge {base_part_name} <- {other_part_name}",
        )
    except GitCommandError as e:
        print(e.stdout)

    return context_info


def prune_tags():
    repo = get_app_repo()

    tags_to_keep: Set[str] = set()
    for head in repo.heads:
        part_type = interpret_part_type(part_name=head.name)
        if part_type == PartType.PART:
            from gitkit.logic.parts import part_tag, parse_part_name

            series_name, part = parse_part_name(head.name)
            tags_to_keep.add(part_tag(series_name, part))
            tags_to_keep.add(series_tag(series_name))
        elif part_type == PartType.CONTEXT:
            tags_to_keep.add(context_tag(head.name))

    repo.delete_tag(
        *(
            tag
            for tag in repo.tags
            if tag.name not in tags_to_keep and tag.name.startswith("(gk)")
        )
    )
