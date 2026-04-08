from gitkit.logic.parts import part_tag
from gitkit.logic.series import context_tag, prune_tags, series_tag, start_series
from gitkit.utils import RepoTester


class TestRepoFunctions(RepoTester):
    def test_prune_tags(self):
        series_name = "test/test-prune-tags"
        start_series(series_name)
        s_tag = series_tag(series_name)
        p_tag = part_tag(series_name, 1.0)

        tags = [
            bad_s_tag := series_tag("fake/test-prune-tags"),
            bad_p_tag := part_tag(series_name, 2.0),
            c_tag := context_tag("context/test-prune-tags"),
            "regular-tag",
        ]

        for tag in tags:
            self.repo.create_tag(tag)

        prune_tags()

        assert s_tag in self.repo.tags
        assert bad_s_tag not in self.repo.tags
        assert p_tag in self.repo.tags
        assert bad_p_tag not in self.repo.tags
        assert c_tag not in self.repo.tags
        assert "regular-tag" in self.repo.tags
