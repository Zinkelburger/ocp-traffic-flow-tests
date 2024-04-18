from common import j2_render, TFT_TOOLS_IMG, PluginOutput, TftAggregateOutput
from logger import logger
from testConfig import TestConfig
from thread import ReturnValueThread
from task import Task
from host import Result
import re
import time


class MeasurePower(Task):
    def __init__(self, tc: TestConfig, node_name: str, tenant: bool):
        super().__init__(tc, 0, node_name, tenant)

        self.in_file_template = "./manifests/tools-pod.yaml.j2"
        self.out_file_yaml = (
            f"./manifests/yamls/tools-pod-{self.node_name}-measure-cpu.yaml"
        )
        self.template_args["pod_name"] = f"tools-pod-{self.node_name}-measure-cpu"
        self.template_args["test_image"] = TFT_TOOLS_IMG

        self.pod_name = self.template_args["pod_name"]
        self.node_name = node_name
        self.cmd = ""

        j2_render(self.in_file_template, self.out_file_yaml, self.template_args)
        logger.info(f"Generated Server Pod Yaml {self.out_file_yaml}")

    def run(self, duration: int) -> None:
        def extract(r: Result) -> int:
            for e in r.out.split("\n"):
                if "Instantaneous power reading" in e:
                    match = re.search(r"\d+", e)
                    if match:
                        return int(match.group())
            logger.error(f"Could not find Instantaneous power reading: {e}.")
            return 0

        def stat(self, cmd: str, duration: int) -> Result:  # type: ignore
            end_time = time.time() + float(duration)
            total_pwr = 0
            iteration = 0
            while True:
                r = self.run_oc(cmd)
                if r.returncode != 0:
                    logger.error(f"Failed to get power {cmd}: {r}")
                pwr = extract(r)
                total_pwr += pwr
                iteration += 1
                # FIXME: Hardcode interval for now
                time.sleep(2)
                if time.time() > end_time:
                    break
            r = Result(f"{total_pwr/iteration}", "", 0)
            return r

        # 1 report at intervals defined by the duration in seconds.
        self.cmd = f"exec -t {self.pod_name} -- ipmitool dcmi power reading"
        self.exec_thread = ReturnValueThread(
            target=stat, args=(self, self.cmd, duration)
        )
        self.exec_thread.start()
        logger.info(f"Running {self.cmd}")

    def output(self, out: TftAggregateOutput) -> None:
        # Return machine-readable output to top level
        assert isinstance(
            self._output, PluginOutput
        ), f"Expected variable to be of type PluginOutput, got {type(self._output)} instead."
        out.plugins.append(self._output)

        # Print summary to console logs
        logger.info(f"measurePower results: {self._output.result}")

    def generate_output(self, data: dict) -> PluginOutput:
        return PluginOutput(
            plugin_metadata={
                "name": "MeasurePower",
                "node_name": self.node_name,
                "pod_name": self.pod_name,
            },
            command=self.cmd,
            result=data,
            name="measure_power",
        )
