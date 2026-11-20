"""film.build.lengths and last_clip: lengths without building."""
from flowreel.film.build import last_clip


def test_last_clip_matches_its_shot_only(tmp_path):
    (tmp_path / "shot_a_b_0123456789abcdef.mp4").write_bytes(b"")
    (tmp_path / "base_a_0123456789abcdef.mp4").write_bytes(b"")
    (tmp_path / "shot_a_0123456789abcdef.part.mp4").write_bytes(b"")
    assert last_clip(tmp_path, "a") is None
    assert last_clip(tmp_path, "a_b").name == "shot_a_b_0123456789abcdef.mp4"
    (tmp_path / "shot_a_fedcba9876543210.mp4").write_bytes(b"")
    assert last_clip(tmp_path, "a").name == "shot_a_fedcba9876543210.mp4"
