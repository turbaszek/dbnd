from pytest import fixture

from dbnd import config
from dbnd._core.configuration.config_readers import read_from_config_stream
from dbnd._core.task_build.task_registry import build_task_from_config
from dbnd._core.utils import seven


test_config = """

[local_machine]
sql_alchemy_conn = aaa
[my_t]
_type=local_machine
sql_alchemy_conn = my_t_sql 


[my_tt]
_from=my_t
sql_alchemy_conn=my_tt_sql

[my_ttt_from_tt]
_from=my_tt
sql_alchemy_conn=my_ttt_from_tt_sql
"""


class TestTaskFromConfig(object):
    @fixture(autouse=True)
    def load_test_config(self):
        ts = read_from_config_stream(seven.StringIO(test_config))
        with config(ts):
            yield ts

    def test_simple_config(self):
        actual = build_task_from_config("my_t")
        assert actual.get_task_family() == "local_machine"
        assert actual.task_name == "my_t"
        assert actual.sql_alchemy_conn == "my_t_sql"

    def test_config_with_from(self):
        actual = build_task_from_config("my_tt")
        assert actual.get_task_family() == "local_machine"
        assert actual.task_name == "my_tt"
        assert actual.sql_alchemy_conn == "my_tt_sql"

    def test_config_with_double_from(self):
        actual = build_task_from_config("my_ttt_from_tt")
        assert actual.get_task_family() == "local_machine"
        assert actual.task_name == "my_ttt_from_tt"
        assert actual.sql_alchemy_conn == "my_ttt_from_tt_sql"
