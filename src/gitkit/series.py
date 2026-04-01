from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from typing import Annotated, List, Optional
from git import Repo, TagReference
from gitkit.utils import gitkit_bail
import typer


app = typer.Typer()


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
    from gitkit.parts import is_part_name_valid

    repo = Repo(".")

    if part_name is None:
        part_name = repo.head.reference.name

    if is_part_name_valid(part_name):
        return PartType.PART

    if part_name in repo.tags:
        return PartType.CONTEXT

    return PartType.OTHER


def load_data_node(*, part_name: Optional[str] = None) -> DataNode | None:
    repo = Repo(".")

    if part_name is None:
        part_name = repo.head.reference.name

    part_type = interpret_part_type(part_name=part_name)

    if part_type == PartType.PART:
        from .parts import parse_part_name

        series_name, _ = parse_part_name(part_name)
        return DataNode(**json.loads(repo.tags[series_tag(series_name)].commit.message))

    if part_type == PartType.CONTEXT:
        return DataNode(**json.loads(repo.tags[part_name].commit.message))

    return None


def save_data_node(node: DataNode, tag_name: str) -> TagReference:
    repo = Repo(".")

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
    return f"{name}-series-info"


def start_series(name: str, *, exists_ok: bool = False, force: bool = False):
    from gitkit.parts import make_part

    repo = Repo(".")

    if (already_exists := series_exists(name)) and exists_ok:
        return

    if not force:
        gitkit_bail(already_exists, f"Series {name} already exists")

    series_info = DataNode(type=DataNodeType.SERIES)

    # if it is a gitkit head, mark it as a series dependency
    # else if it is a context commit, use its dependencies
    current_part_type = interpret_part_type()
    if current_part_type == PartType.PART:
        series_info.dependent_on = [repo.head.reference.name]
    elif current_part_type == PartType.CONTEXT:
        context_info = load_data_node()
        gitkit_bail(context_info is None, "Could not find data node for this context")
        series_info.dependent_on = context_info.dependent_on

    save_data_node(series_info, series_tag(name))

    make_part(1.0, on_series=name)


def series_exists(name: str) -> bool:
    repo = Repo(".")
    return series_tag(name) in [tag.name for tag in repo.tags]


def create_context(other_part_name: str, *, name: Optional[str] = None) -> DataNode:
    repo = Repo(".")

    def get_dependencies(part_name: str) -> List[str]:
        part_type = interpret_part_type(part_name=part_name)
        gitkit_bail(
            part_type == PartType.OTHER,
            "Cannot make context where the base is not a gitkit managed head. Try making a series instead.",
        )

        if part_type == PartType.PART:
            return [part_name]
        elif part_type == PartType.CONTEXT:
            node = load_data_node(part_name=part_name)
            gitkit_bail(node is None, f"Cannot find data node for context {part_name}")
            return node.dependent_on

        return []

    base_part_name = repo.head.reference.name

    base_dependencies = get_dependencies(base_part_name)
    other_dependencies = get_dependencies(other_part_name)

    context_info = DataNode(
        type=DataNodeType.CONTEXT, dependent_on=base_dependencies + other_dependencies
    )

    if name is None:
        chars = (
            ((ord(a) ^ ord(b)) % (0x7E - 0x21)) + 0x21
            for a, b in zip(base_part_name, other_part_name)
        )
        name = "".join([chr(char) for char in chars])

    save_data_node(context_info, name)

    context_head = repo.create_head(name)
    context_head.checkout()

    repo.git.merge(
        other_part_name,
        m=f"(gitkit) context merge {base_part_name} <- {other_part_name}",
    )

    return context_info


def prune_tags():
    repo = Repo(".")

    tags_to_keep = set()
    for head in repo.heads:
        tag = None

        part_type = interpret_part_type(part_name=head.name)
        if part_type == PartType.PART:
            from .parts import part_tag, parse_part_name

            series_name, part = parse_part_name(head.name)
            tag = part_tag(series_name, part)
        elif part_type == PartType.CONTEXT:
            tag = head.name

        if tag is not None and tag in repo.tags:
            tags_to_keep.add(repo.tags[tag])

    repo.delete_tag(*(tag for tag in repo.tags if tag not in tags_to_keep))


@app.command(help="Start a new series", rich_help_panel="Series")
def startseries(
    name: Annotated[str, typer.Argument(help="The name of the series to create")],
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Whether to force the creation of this series"
        ),
    ] = False,
):
    start_series(name, force=force)


@app.command(
    help="Get either: 1) information stored on this part's series's data node or 2) information on this context's data node",
    rich_help_panel="Series",
)
def nodeinfo():
    node = load_data_node()
    gitkit_bail(node is None, "Couldn't find data node for the current part")
    print(json.dumps(asdict(node), indent=2))


@app.command(
    help="Create a new context head from the combination of the current part and another given part",
    rich_help_panel="Series",
)
def newcontext(
    other: Annotated[
        str, typer.Argument(..., help="The other part to combine with the current part")
    ],
    name: Annotated[
        Optional[str],
        typer.Option(
            ...,
            help="The name to give this context, if you'd like to keep better track",
        ),
    ] = None,
):
    create_context(other, name=name)


@app.command(
    help="Remove tags that are for parts, series, or contexts which no longer exist",
    rich_help_panel="Utilities",
)
def prune():
    prune_tags()
