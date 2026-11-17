import pytest

from flowreel.scene.errors import Checker, ConfigError, format_path


def test_path_format():
    assert format_path(("layers", 2, "level")) == "layers[2].level"
    assert format_path(()) == ""


def test_error_names_file_and_path():
    err = Checker("bare.yml").at("camera", "view").error("bad")
    assert str(err) == "bare.yml: camera.view: bad"


def test_unknown_key_suggests_nearest():
    with pytest.raises(ConfigError, match=r"shot.yml: antialais: unknown key.*did you mean 'antialias'"):
        Checker("shot.yml").mapping({"antialais": "ssaa"}, ["name", "antialias"])


def test_unknown_key_without_close_match_has_no_hint():
    with pytest.raises(ConfigError) as exc:
        Checker().mapping({"zzz": 1}, ["name"])
    assert "did you mean" not in str(exc.value) and "allowed: name" in str(exc.value)


def test_missing_required_key():
    with pytest.raises(ConfigError, match="missing key 'source'"):
        Checker("a.yml").mapping({"name": "x"}, ["name", "source"], required=["source"])


def test_not_a_mapping_and_not_a_list():
    with pytest.raises(ConfigError, match="expected a mapping, got a list"):
        Checker().mapping([1], [])
    with pytest.raises(ConfigError, match="expected a list, got 3"):
        Checker().sequence(3)


def test_choice_suggests():
    with pytest.raises(ConfigError, match="did you mean 'smooth'"):
        Checker().choice("smoth", ["linear", "smooth"])


@pytest.mark.parametrize("bad", [True, "3", None, float("nan")])
def test_number_rejects(bad):
    with pytest.raises(ConfigError):
        Checker().number(bad)


def test_numbers_count_and_path():
    c = Checker("f.yml").at("size")
    assert c.numbers([1, 2], 2) == (1.0, 2.0)
    with pytest.raises(ConfigError, match=r"f.yml: size\[1\]: expected a number"):
        c.numbers([1, "a"], 2)


def test_integer():
    assert Checker().integer(5, minimum=1) == 5
    with pytest.raises(ConfigError, match="at least 1"):
        Checker().integer(0, minimum=1)
    with pytest.raises(ConfigError):
        Checker().integer(1.5)
