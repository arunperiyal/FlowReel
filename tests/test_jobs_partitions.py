"""jobs.partitions: the cluster table, times and memory in Slurm's forms."""
import pytest
import yaml

from flowreel.jobs import partitions as p
from flowreel.scene.errors import ConfigError

GB = 1024 ** 3


@pytest.mark.parametrize("text, seconds", [
    ("90", 5400), ("90:30", 5430), ("02:30:00", 9000), ("1-12", 129600),
    ("1-12:30", 131400), ("2-00:00:05", 172805), ("90m", 5400), ("3h", 10800),
    ("1.5h", 5400), ("2d", 172800), ("45s", 45), (180, 10800)])
def test_parse_time(text, seconds):
    assert p.parse_time(text) == seconds


def test_format_time_and_bad_times():
    assert p.format_time(9000) == "02:30:00"
    assert p.format_time(259200) == "3-00:00:00"
    assert p.format_time(86400 + 61) == "1-00:01:01"
    with pytest.raises(ValueError, match="not a time"):
        p.parse_time("soon")


@pytest.mark.parametrize("text, nbytes", [
    ("32G", 32 * GB), ("125 GB", 125 * GB), ("500M", 500 * 1024 ** 2), ("1.5T", int(1.5 * 1024 * GB)),
    ("2048", 2 * GB), ("512k", 512 * 1024)])
def test_parse_memory(text, nbytes):
    assert p.parse_memory(text) == nbytes


def test_format_memory():
    assert p.format_memory(32 * GB) == "32G"
    assert p.format_memory(int(1.5 * GB)) == "1536M"
    assert p.format_memory(1024 ** 2 + 1) == "2M"          # rounded up, never less


def test_the_table():
    clusters = p.load(user=p.Path("/nonexistent.yml"))
    air = clusters["airavata"]
    assert list(air.partitions) == ["part1", "part2", "part3"]
    part3 = air.partition("part3")
    assert (part3.time, part3.cpus, part3.memory, part3.shared) == (259200, 128, 125 * GB, True)
    shared = clusters["param_shakti"].partition("shared")
    assert (shared.cpus, shared.job_cpus, shared.memory) == (40, 36, None)
    with pytest.raises(KeyError, match="partitions: part1, part2, part3"):
        air.partition("part9")


def test_fitting_picks_the_shortest_that_takes_the_job():
    air = p.load(user=p.Path("/nonexistent.yml"))["airavata"]
    assert air.fitting(3600).name == "part1"
    assert air.fitting(4 * 3600, 16, 64 * GB).name == "part2"
    assert air.fitting(48 * 3600).name == "part3"
    with pytest.raises(ValueError, match="no partition of airavata takes 4-00:00:00"):
        air.fitting(96 * 3600)
    with pytest.raises(ValueError, match="200 cores"):
        air.fitting(3600, 200)
    shakti = p.load(user=p.Path("/nonexistent.yml"))["param_shakti"]
    assert shakti.fitting(3600, 30).name == "shared"            # shared before exclusive
    assert shakti.fitting(3600, 38).name == "medium"            # more than shared's 36


def test_find_by_name_environment_or_host():
    clusters = p.load(user=p.Path("/nonexistent.yml"))
    assert p.find("param_shakti", clusters, environ={}).name == "param_shakti"
    assert p.find(None, clusters, environ={"FLOWREEL_CLUSTER": "param_shakti"},
                  host="node1").name == "param_shakti"
    assert p.find(None, clusters, environ={}, host="node1").name == "airavata"
    assert p.find(None, clusters, environ={}, host="airavata.iitkgp.ac.in").name == "airavata"
    with pytest.raises(LookupError, match="laptop.*--cluster NAME"):
        p.find(None, clusters, environ={}, host="laptop")
    with pytest.raises(LookupError, match="no cluster 'moon'"):
        p.find("moon", clusters, environ={})


def test_a_user_table_adds_and_overrides(tmp_path):
    user = tmp_path / "partitions.yml"
    user.write_text(yaml.safe_dump({
        "airavata": {"partitions": {"part1": {"time": "6h", "cpus": 64, "memory": "60G"}}},
        "workstation": {"hosts": ["ws*"], "partitions": {"local": {"time": "7d", "cpus": 48}}}}))
    clusters = p.load(user=user)
    air = clusters["airavata"]
    assert air.partition("part1").time == 6 * 3600 and air.partition("part1").cpus == 64
    assert air.partition("part3").time == 259200 and air.hosts       # the rest kept
    assert p.find(None, clusters, environ={}, host="ws01").name == "workstation"


def test_a_bad_user_table_names_the_file_and_key(tmp_path):
    user = tmp_path / "partitions.yml"
    user.write_text(yaml.safe_dump({"airavata": {"partitions": {"part1": {"tme": "6h"}}}}))
    with pytest.raises(ConfigError, match=r"partitions.yml.*part1.*tme.*did you mean 'time'"):
        p.load(user=user)
    user.write_text(yaml.safe_dump({"airavata": {"partitions": {"p": {"time": "soon"}}}}))
    with pytest.raises(ConfigError, match="not a time: 'soon'"):
        p.load(user=user)
