import pytest

from polygon_streamer.single_instance import SingleInstanceError, single_instance


def test_single_instance_blocks_second_holder(tmp_path):
    lock = tmp_path / "streamer.lock"
    with single_instance(lock):
        with pytest.raises(SingleInstanceError):
            with single_instance(lock):
                pass
