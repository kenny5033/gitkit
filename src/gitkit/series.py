from dataclasses import asdict, dataclass, field
import json
from typing import Annotated, List, Optional
from git import Repo
from gitkit.utils import gitkit_bail
import typer


app = typer.Typer()


@dataclass
class SeriesInfo:
    dependent_on: List[str] = field(default_factory=list)


def series_tag(name: str) -> str:
    return f"{name}-series-info"


def start_series(name: str, *, exists_ok: bool = False, force: bool = False):
    from gitkit.parts import make_part, is_part_name_valid

    repo = Repo(".")

    if (already_exists := series_exists(name)) and exists_ok:
        return

    if not force:
        gitkit_bail(already_exists, f"Series {name} already exists")

    series_info = SeriesInfo()

    old_head = repo.head.reference

    # if it is a gitkit head, mark it as a series dependency
    # else if it is a context commit, use its dependencies
    if is_part_name_valid(old_head.name):
        series_info.dependent_on = [old_head.name]
    elif old_head.name in repo.tags:
        # if a head's name is in tags, it is a context
        context_info = json.loads(old_head.commit.message)
        series_info.dependent_on = context_info["dependent_on"]

    series_head = repo.create_head(name)
    series_head.checkout()

    info = asdict(series_info)
    repo.git.commit("--allow-empty", "-m", json.dumps(info))
    repo.create_tag(series_tag(name), series_head, force=True)

    old_head.checkout()
    repo.delete_head(series_head, force=True)

    make_part(1.0, on_series=name)


def get_series_info(*, series_name: Optional[str] = None) -> SeriesInfo:
    from .parts import parse_part_name

    repo = Repo(".")

    if series_name is None:
        series_name, _ = parse_part_name(repo.head.reference.name)

    info = SeriesInfo(**json.loads(repo.tags[series_tag(series_name)].commit.message))
    return info


def series_exists(name: str) -> bool:
    repo = Repo(".")
    return series_tag(name) in [tag.name for tag in repo.tags]


def create_context(other: str, *, name: Optional[str] = None) -> SeriesInfo:
    from .parts import parse_part_name, is_part_name_valid

    repo = Repo(".")

    other_name, _ = parse_part_name(other)

    base_part_name = repo.head.reference.name
    if is_part_name_valid(base_part_name):
        base_name, _ = parse_part_name(base_part_name)
        base_info = get_series_info(series_name=base_name)
        base_dependencies = [base_part_name]
    else:
        # the base is a context in of itself
        base_name = base_part_name
        base_info = SeriesInfo(**json.loads(repo.head.reference.commit.message))
        base_dependencies = base_info.dependent_on

    context_info = SeriesInfo(dependent_on=base_dependencies + [other])
    info = asdict(context_info)

    if name is None:
        chars = (
            ((ord(a) ^ ord(b)) % (0x7E - 0x21)) + 0x21
            for a, b in zip(base_name, other_name)
        )
        name = "".join([chr(char) for char in chars])

    context_head = repo.create_head(name)
    context_head.checkout()
    repo.git.commit("--allow-empty", "-m", json.dumps(info))
    repo.create_tag(name, context_head, force=True)

    return context_info


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
    help="Get information stored on the series's information commit",
    rich_help_panel="Series",
)
def seriesinfo():
    print(json.dumps(asdict(get_series_info()), indent=2))


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
