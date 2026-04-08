from base64 import b64encode
from gitkit.logic.parts import (
    construct_base,
    generate_part_name,
    get_current_part,
    get_parts_in_series,
    is_part_name_valid,
    make_part,
    parse_part_name,
    part_tag,
)
from gitkit.logic.series import start_series
from gitkit.utils import RepoTester
import pytest


def test_part_tag():
    series_name = "test/part-tag"
    part = 1.0
    res = part_tag(series_name, part)

    base64_name = b64encode(series_name.encode()).decode()
    assert res == f"(gk)p1.0-base({base64_name})"


def test_generate_part_name():
    name = "test/generate-part-name"
    part = 1.0
    res = generate_part_name(name, part)

    assert res == "test/generate-part-name-p1.0"


def test_is_part_name_valid():
    part_name = "test/is-part-name-valid-p1.0"
    res = is_part_name_valid(part_name)

    assert res

    bad_part_name = "this-aint-valid"
    res = is_part_name_valid(bad_part_name)

    assert not res


def test_parse_part_name():
    part_name = "test/parse-part-name-p1.0"
    series_name, part = parse_part_name(part_name)

    assert series_name == "test/parse-part-name"
    assert part == 1.0

    bad_part_name = "very-baddy"
    with pytest.raises(ValueError, match=r"could not be parsed"):
        parse_part_name(bad_part_name)


class TestRepoFunctions(RepoTester):
    def test_make_part(self):
        series_name = "test/make-part"
        start_series(series_name, exists_ok=True)
        make_part(2.0)

        assert "test/make-part-p2.0" == self.repo.head.reference.name
        assert (tag := part_tag(series_name, 2.0)) in self.repo.tags
        assert self.repo.tags[tag].commit.hexsha == self.repo.head.commit.hexsha

    def test_construct_base(self):
        series_name = "test/construct-base"
        part = 1.0
        construct_base(series_name, part)

        assert (
            self.repo.head.commit.message.strip()
            == "(gitkit) init test/construct-base part 1.0"
        )
        assert (tag := part_tag(series_name, part)) in self.repo.tags
        assert self.repo.tags[tag].commit.hexsha == self.repo.head.commit.hexsha

    def test_get_current_part(self):
        series_name = "test/get-current-part"
        start_series(series_name, exists_ok=True)
        make_part(2.0)

        res = get_current_part()
        assert (tag := self.repo.tags[part_tag(series_name, 2.0)]) == res

        self.repo.delete_tag(tag)

        res = get_current_part()
        assert res is None

    def test_get_parts_in_series(self):
        series_name = "test/get-parts-in-series"
        start_series(series_name, exists_ok=True)
        make_part(2.0)
        make_part(2.1)
        make_part(3.0)

        res = get_parts_in_series(series_name)

        assert res[0] == 1.0
        assert res[1] == 2.0
        assert res[2] == 2.1
        assert res[3] == 3.0
