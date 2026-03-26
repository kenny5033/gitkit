from base64 import b64encode
from dataclasses import dataclass
import re
from typing import Annotated, List, Optional, Tuple
from git import GitCommandError, Head, Repo, TagReference
from gitkit.utils import gitkit_bail
import typer

app = typer.Typer()

part_name_regex = re.compile(r"(.*)-p(\d+(?:\.\d*)?)")


def part_tag(series_name: str, part: float) -> str:
    base64_name = b64encode(series_name.encode())
    return f"p{part}-base({base64_name.decode()})"


def generate_part_name(name: str, part: float) -> str:
    return f"{name}-p{part}"


def parse_part_name(part_name: str) -> Tuple[str, float]:
    match = re.fullmatch(part_name_regex, part_name)

    gitkit_bail(
        not match,
        f"Part name '{part_name}' could not be parsed",
    )

    name, part = match.groups()
    return name, float(part)


def construct_base(series_name: str, part: float):
    repo = Repo(".")

    repo.git.commit(allow_empty=True, m=f"(gitkit) init {series_name} part {part}")
    repo.create_tag(part_tag(series_name, part), force=True)


def get_current_part() -> TagReference:
    repo = Repo(".")

    name, part = parse_part_name(repo.head.reference.name)
    return repo.tags[part_tag(name, part)]


def make_part(
    part: float,
    last_commit_hash: Optional[str] = None,
    *,
    on_series: Optional[str] = None,
):
    repo = Repo(".")

    if on_series is None:
        part_name = repo.head.reference.name
        series_name, prev_part = parse_part_name(part_name)
    else:
        # this call is meant to be manually attached to a series
        from .series import series_exists

        gitkit_bail(
            not series_exists(on_series),
            f"Cannot attach to series {on_series} because it doesn't exist",
        )
        series_name, prev_part = on_series, 0

    gitkit_bail(part <= prev_part, "The new part must come after the current part")

    # ensure the part name is availabled
    part_name = generate_part_name(series_name, part)
    gitkit_bail(
        part_name in [head.name for head in repo.heads], "This part already exists"
    )

    new_branch = repo.create_head(part_name, force=True)

    if last_commit_hash is not None:
        repo.git.reset("--hard", last_commit_hash)
        (tmp_head := repo.create_head("gitkit/tmp")).checkout()

        construct_base(series_name, part)

        new_branch.checkout()
        repo.git.rebase(last_commit_hash, onto=tmp_head.commit.hexsha, keep_empty=True)

        repo.delete_head(tmp_head)
    else:
        new_branch.checkout()
        construct_base(series_name, part)


def get_parts_in_series(series_name: str) -> List[float]:
    repo = Repo(".")

    def filter_heads(head: Head):
        return head.name.startswith(series_name)

    def map_heads(head: Head):
        _, part = parse_part_name(head.name)
        return part

    parts = list(map(map_heads, filter(filter_heads, repo.heads)))
    parts.sort()

    return parts


def rebase_part(onto: str):
    from gitkit.series import get_series_info

    (repo := Repo(".")).git.fetch()

    part_name = repo.head.reference.name
    name, current_part = parse_part_name(part_name)

    parts = get_parts_in_series(name)
    unmerged_dependencies = [part for part in parts if int(part) < int(current_part)]

    gitkit_bail(
        len(unmerged_dependencies) > 0,
        f"There are unclosed parts which come before this part: {unmerged_dependencies}",
    )

    series_dependency: str | None = get_series_info().get("dependent_on")
    if series_dependency is not None:
        gitkit_bail(
            series_dependency in repo.heads,
            f"Series dependency {series_dependency} has not been closed",
        )

    try:
        repo.git.rebase(part_tag(name, current_part), onto=onto)
    except GitCommandError as e:
        print(e.stderr)


@dataclass
class PartStats:
    lines_added: int
    lines_removed: int

    @property
    def total_lines_changed(self) -> int:
        return self.lines_added + self.lines_removed


def part_stats(*, up_to: Optional[str] = None):
    repo = Repo(".")

    part = get_current_part()

    diff = repo.git.diff(part.commit.hexsha, up_to, numstat=True, z=True)

    total_added = 0
    total_removed = 0

    info_lines: list = diff.strip().split("\0")[:-1]

    for added, removed, file_name in (line.split("\t") for line in info_lines):
        total_added += int(added)
        total_removed += int(removed)

    return PartStats(lines_added=total_added, lines_removed=total_removed)


@app.command(help="Make a new part in the current series", rich_help_panel="Parts")
def makepart(
    part: Annotated[
        float,
        typer.Argument(
            ...,
            help="This branch's *numeric* identifier in a series of stacked branches, e.g. 1 or 2.5",
        ),
    ],
    last_commit: Annotated[
        Optional[str],
        typer.Argument(
            help="The last commit to include before the base of the new part",
        ),
    ] = None,
    series: Annotated[
        Optional[str],
        typer.Option(
            "--series",
            "-s",
            help="Manually override the series for this part. Will create the series if it doesn't already exist",
        ),
    ] = None,
):
    if series is not None:
        from .series import start_series

        start_series(series, exists_ok=True)

    make_part(part, last_commit, on_series=series)


@app.command(help="Rebase the current part", rich_help_panel="Parts")
def rebase(
    onto: Annotated[
        str,
        typer.Argument(..., help="The onto argument for the rebase"),
    ] = "origin/master",
):
    rebase_part(onto)


@app.command(help="Get stats on lines changed", rich_help_panel="Parts")
def partstats(
    up_to: Annotated[
        Optional[str],
        typer.Argument(
            ..., help="The commit to go no further than for calculating line stats"
        ),
    ] = None,
):
    stats = part_stats(up_to=up_to)
    print()
    print("Part Stats")
    print("----------")
    print(f"Lines Added:         {stats.lines_added:>5}")
    print(f"Lines Removed:       {stats.lines_removed:>5}")
    print(f"Total Lines Changed: {stats.total_lines_changed:>5}")
    print()
