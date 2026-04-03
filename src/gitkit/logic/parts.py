from base64 import b64encode
from dataclasses import dataclass
import re
from typing import List, Optional, Tuple
from git import GitCommandError, Head, Repo, TagReference
from gitkit.utils import gitkit_bail


part_name_regex = re.compile(r"(.*)-p(\d+(?:\.\d*)?)")


@dataclass
class PartStats:
    lines_added: int
    lines_removed: int

    @property
    def total_lines_changed(self) -> int:
        return self.lines_added + self.lines_removed


def part_tag(series_name: str, part: float) -> str:
    base64_name = b64encode(series_name.encode())
    return f"(gk)p{part}-base({base64_name.decode()})"


def generate_part_name(name: str, part: float) -> str:
    return f"{name}-p{part}"


def is_part_name_valid(part_name: str) -> bool:
    return bool(re.fullmatch(part_name_regex, part_name))


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


def get_current_part() -> TagReference | None:
    repo = Repo(".")

    name, part = parse_part_name(repo.head.reference.name)
    if (tag := part_tag(name, part)) in repo.tags:
        return repo.tags[tag]

    return None


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
        from gitkit.logic.series import series_exists, start_series

        if not series_exists(on_series):
            start_series(on_series)

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


def rebase_part(onto: str, *, context_only: bool = False):
    from gitkit.logic.series import load_data_node, interpret_part_type, PartType

    (repo := Repo(".")).git.fetch()

    part_type = interpret_part_type()
    gitkit_bail(part_type == PartType.CONTEXT, "Contexts cannot be rebased")
    gitkit_bail(part_type != PartType.PART, "This is not a valid gitkit part")

    part_name = repo.head.reference.name
    name, current_part = parse_part_name(part_name)
    parts = get_parts_in_series(name)
    unmerged_dependencies = [part for part in parts if int(part) < int(current_part)]

    gitkit_bail(
        len(unmerged_dependencies) > 0,
        f"There are unclosed parts which come before this part: {unmerged_dependencies}",
    )

    if context_only:
        tag = get_current_part()
        if tag is None:
            merge_base_sha = repo.git.merge_base(onto, part_name)

            try:
                repo.git.rebase(merge_base_sha, onto=onto)
            except GitCommandError as e:
                gitkit_bail(True, e.stderr)
        else:
            gitkit_bail(True, "This part's base has not yet been rebased")

        return

    series_dependencies = load_data_node().dependent_on
    for dependency in series_dependencies:
        gitkit_bail(
            dependency in repo.heads,
            f"Series dependencies {series_dependencies} have not all been closed",
        )

    try:
        tag = get_current_part()
        gitkit_bail(tag is None, "Could not find this part's base")

        repo.git.rebase(tag, onto=onto)
        repo.delete_tag(tag)
    except GitCommandError as e:
        gitkit_bail(True, e.stderr)


def part_stats(*, up_to: Optional[str] = None, fall_back_onto: str) -> PartStats:
    repo = Repo(".")

    part = get_current_part()
    if part is None:
        base_sha = repo.git.merge_base(fall_back_onto, repo.head.reference.name)
    else:
        base_sha = part.commit.hexsha

    diff = repo.git.diff(base_sha, up_to, numstat=True, z=True)

    total_added = 0
    total_removed = 0

    info_lines: list = diff.strip().split("\0")[:-1]

    for added, removed, file_name in (line.split("\t") for line in info_lines):
        total_added += int(added)
        total_removed += int(removed)

    return PartStats(lines_added=total_added, lines_removed=total_removed)
