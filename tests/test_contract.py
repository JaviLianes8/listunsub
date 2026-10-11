import importlib.resources

import listunsub

PUBLIC_API: list[str] = [
    "ONE_CLICK_POST",
    "build",
    "http_links",
    "is_one_click",
    "mailto_links",
    "one_click_post",
    "parse",
]


def test_all_lists_exactly_the_public_api() -> None:
    assert sorted(listunsub.__all__) == sorted(PUBLIC_API)


def test_every_exported_name_resolves() -> None:
    for name in listunsub.__all__:
        assert hasattr(listunsub, name)


def test_version_is_a_three_part_string() -> None:
    parts = listunsub.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_the_package_ships_type_information() -> None:
    assert importlib.resources.files("listunsub").joinpath("py.typed").is_file()
