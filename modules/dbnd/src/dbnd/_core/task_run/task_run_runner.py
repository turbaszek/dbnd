import logging
import signal
import typing

from dbnd._core.constants import SystemTaskName, TaskRunState
from dbnd._core.errors import friendly_error, show_error_once
from dbnd._core.errors.base import DatabandSigTermError
from dbnd._core.plugin.dbnd_plugins import pm
from dbnd._core.task_build.task_context import TaskContextPhase
from dbnd._core.task_run.task_run_ctrl import TaskRunCtrl
from dbnd._core.task_run.task_run_error import TaskRunError
from dbnd._core.utils.basics.nested_context import nested
from dbnd._core.utils.basics.safe_signal import safe_signal
from dbnd._core.utils.seven import contextlib
from dbnd._core.utils.timezone import utcnow
from dbnd._core.utils.traversing import traverse_to_str


if typing.TYPE_CHECKING:
    from dbnd import Task

logger = logging.getLogger(__name__)


class TaskRunRunner(TaskRunCtrl):
    @contextlib.contextmanager
    def task_run_execution_context(self):
        ctx_managers = [
            self.task.ctrl.task_context(phase=TaskContextPhase.RUN),
            self.task_run.log.capture_task_log(),
        ]
        ctx_managers += pm.hook.dbnd_task_run_context(task_run=self.task_run)
        with nested(*ctx_managers):
            yield

    def execute(self, airflow_context=None, allow_resubmit=True):
        self.task_run.airflow_context = airflow_context
        task_run = self.task_run
        task = self.task  # type: Task
        task_engine = task_run.task_engine
        if allow_resubmit and task_engine._should_wrap_with_submit_task(task_run):
            args = task_engine.dbnd_executable + [
                "execute",
                "--dbnd-run",
                str(task_run.run.driver_dump),
                "task_execute",
                "--task-id",
                task_run.task.task_id,
            ]
            submit_task = self.task_run.task_engine.submit_to_engine_task(
                env=task.task_env, task_name=SystemTaskName.task_submit, args=args
            )
            submit_task.task_meta.add_child(task.task_id)
            task_run.run.run_dynamic_task(submit_task)
            return

        with self.task_run_execution_context():
            if task_run.run.is_killed():
                raise friendly_error.task_execution.databand_context_killed(
                    "task.execute_start of %s" % task
                )
            original_sigterm_signal = None
            try:

                def signal_handler(signum, frame):
                    logger.info("Task runner received signal. Exiting...")
                    task_run.run._internal_kill()
                    raise DatabandSigTermError(
                        "Task received signal", help_msg="Probably the job was canceled"
                    )

                original_sigterm_signal = safe_signal(signal.SIGTERM, signal_handler)

                task_run.start_time = utcnow()
                self.task_env.prepare_env()
                if task._complete():
                    task_run.set_task_reused()
                    return

                if not self.task.ctrl.should_run():
                    self.task.ctrl.validator.validate_task_inputs()

                self.ctrl.validator.validate_task_is_ready_to_run()

                task_run.set_task_run_state(state=TaskRunState.RUNNING)
                try:
                    result = self.task._task_submit()
                    self.ctrl.save_task_band()
                    self.ctrl.validator.validate_task_is_complete()
                finally:
                    self.task_run.finished_time = utcnow()

                task_run.set_task_run_state(TaskRunState.SUCCESS)
                task_run.run.cleanup_after_task_run(task)

                return result
            except DatabandSigTermError as ex:
                logger.error(
                    "Sig TERM! Killing the task '%s' via task.on_kill()",
                    task_run.task.task_id,
                )
                error = TaskRunError.buid_from_ex(ex, task_run)
                try:
                    task.on_kill()
                except Exception:
                    logger.exception("Failed to kill task on user keyboard interrupt")
                task_run.set_task_run_state(TaskRunState.CANCELLED, error=error)
                raise
            except KeyboardInterrupt as ex:
                logger.error(
                    "User Interrupt! Killing the task %s", task_run.task.task_id
                )
                error = TaskRunError.buid_from_ex(ex, task_run)
                try:
                    if task._conf_confirm_on_kill_msg:
                        from dbnd._vendor import click

                        if click.confirm(task._conf_confirm_on_kill_msg, default=True):
                            task.on_kill()
                        else:
                            logger.warning(
                                "Task is not killed accordingly to user input!"
                            )
                    else:
                        task.on_kill()
                except Exception:
                    logger.exception("Failed to kill task on user keyboard interrupt")
                task_run.set_task_run_state(TaskRunState.CANCELLED, error=error)
                task_run.run._internal_kill()
                raise
            except SystemExit as ex:
                error = TaskRunError.buid_from_ex(ex, task_run)
                task_run.set_task_run_state(TaskRunState.CANCELLED, error=error)
                raise friendly_error.task_execution.system_exit_at_task_run(task, ex)
            except Exception as ex:
                error = TaskRunError.buid_from_ex(ex, task_run)
                task_run.set_task_run_state(TaskRunState.FAILED, error=error)
                show_error_once.set_shown(ex)
                raise
            finally:
                task_run.airflow_context = None
                if original_sigterm_signal:
                    safe_signal(signal.SIGTERM, original_sigterm_signal)

    def _save_task_band(self):
        if self.task.task_band:
            task_outputs = traverse_to_str(self.task.task_outputs)
            self.task.task_band.as_object.write_json(task_outputs)
