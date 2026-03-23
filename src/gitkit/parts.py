from base64 import b64encode
from functools import reduce
import re
from typing import Annotated, List, Optional, Tuple
from git import GitCommandError, Head, Repo
import typer

app = typer.Typer()

part_name_regex = re.compile(r"(.*)-p(\d+(?:\.\d*)?)")


def part_tag(series_name: str, part: float) -> str:
    base64_name = b64encode(series_name.encode())
    return f"p{part}-base({base64_name.decode()})"


def generate_part_name(name: str, part: float) -> str:
    return f"{name}-p{part}"


def parse_part_name(part_name: str) -> Tuple[str, float]:
    assert (match := re.fullmatch(part_name_regex, part_name))

    name, part = match.groups()
    return name, float(part)


def construct_base(series_name: str, part: float):
    repo = Repo(".")

    repo.git.commit(allow_empty=True, m=f"(gitkit) init {series_name} part {part}")
    repo.create_tag(part_tag(series_name, part), force=True)


def make_part(
    part: float,
    last_commit_hash: Optional[str] = None,
    *,
    begins_series_name: Optional[str] = None,
):
    repo = Repo(".")

    if begins_series_name is None:
        part_name = repo.head.reference.name
        series_name, prev_part = parse_part_name(part_name)
    else:
        # this call is meant to begin a series
        series_name, prev_part = begins_series_name, 0

    assert part > prev_part, "The new part must come after the current part"

    new_branch = repo.create_head(generate_part_name(series_name, part), force=True)

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


@app.command(help="Make a new part in the current series")
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
):
    make_part(part, last_commit)


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
    (repo := Repo(".")).git.fetch()

    part_name = repo.head.reference.name
    name, current_part = parse_part_name(part_name)

    parts = get_parts_in_series(name)
    unmerged_dependencies = [part for part in parts if int(part) < int(current_part)]

    assert len(unmerged_dependencies) == 0, (
        f"There are parts this part relies on that have not been closed: {unmerged_dependencies}"
    )

    try:
        repo.git.rebase(part_tag(name, current_part), onto=onto)
    except GitCommandError as e:
        print(e.stderr)


@app.command(help="Rebase the current part")
def rebase(
    onto: Annotated[
        str,
        typer.Argument(..., help="The onto argument for the rebase"),
    ] = "origin/master",
):
    rebase_part(onto)
