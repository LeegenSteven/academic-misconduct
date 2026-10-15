"""Standard-library regression checks for the portable command entry point.

All subprocess calls are mocked: no tokenizer, model, GPU, or training is used.
Run from the repository root with:
    python code/shared/route1_qwen38/test_run_route1_v2.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
ENTRY_PATH = ROOT / "code/ly/run_route1_v2.py"
SPEC = importlib.util.spec_from_file_location("route1_v2_entry_under_test", ENTRY_PATH)
ENTRY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENTRY)


def option(command, name):
    return command[command.index(name) + 1]


class EntryPointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="route1_cli_test_")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.model = self.folder / "official_model"
        self.output = self.folder / "runs"

    def commands(self, *arguments):
        with mock.patch.object(sys, "argv", [str(ENTRY_PATH), *arguments]), \
                mock.patch.object(ENTRY.subprocess, "run") as run, \
                contextlib.redirect_stdout(io.StringIO()):
            ENTRY.main()
        for call in run.call_args_list:
            self.assertEqual(call.kwargs, {"cwd": ROOT, "check": True})
        return [call.args[0] for call in run.call_args_list]

    def common(self, stage):
        return ["--stage", stage, "--model-path", str(self.model), "--output-root", str(self.output)]

    def prepare_default_adapters(self):
        for name in ("Mbio", "Mscv"):
            (self.output / "train" / name / "final_adapter").mkdir(parents=True)

    def test_smoke_reloads_each_saved_final_adapter(self):
        commands = self.commands(*self.common("smoke"))
        self.assertEqual(len(commands), 4)
        for index, dataset in enumerate(("sciciteval", "sarol")):
            training, evaluation = commands[index * 2:index * 2 + 2]
            self.assertEqual(Path(training[1]), ENTRY.TRAINERS[dataset])
            self.assertEqual(option(training, "--epochs"), "1")
            self.assertEqual(Path(option(evaluation, "--adapter")),
                             Path(option(training, "--output-dir")) / "final_adapter")
            self.assertEqual(option(evaluation, "--split"), "train")
            self.assertEqual(Path(option(evaluation, "--inputs")).name, "smoke32.inputs.jsonl")

    def test_dev_and_test_default_final_adapters(self):
        self.prepare_default_adapters()
        for stage in ("dev", "test"):
            with self.subTest(stage=stage):
                commands = self.commands(*self.common(stage), "--models", "M0", "Mbio", "Mscv")
                self.assertEqual(len(commands), 6)
                self.assertEqual(sum(option(command, "--model-name") == "M0" for command in commands), 2)
                for command in commands:
                    model_name = option(command, "--model-name")
                    self.assertEqual(option(command, "--split"), stage)
                    if model_name == "M0":
                        self.assertNotIn("--adapter", command)
                    else:
                        self.assertEqual(Path(option(command, "--adapter")),
                                         self.output / "train" / model_name / "final_adapter")

    def test_explicit_checkpoint_paths_are_not_extended(self):
        checkpoints = {"Mbio": self.folder / "selected_bio_checkpoint",
                       "Mscv": self.folder / "selected_scv_checkpoint"}
        for checkpoint in checkpoints.values():
            checkpoint.mkdir()
        for stage in ("dev", "test"):
            with self.subTest(stage=stage):
                commands = self.commands(*self.common(stage), "--models", "Mbio", "Mscv",
                                         "--mbio-adapter", str(checkpoints["Mbio"]),
                                         "--mscv-adapter", str(checkpoints["Mscv"]))
                self.assertEqual(len(commands), 4)
                for command in commands:
                    self.assertEqual(Path(option(command, "--adapter")),
                                     checkpoints[option(command, "--model-name")])

    def test_verify_requires_no_model_and_only_calls_validator(self):
        commands = self.commands("--stage", "verify")
        self.assertEqual(len(commands), 1)
        self.assertEqual(Path(commands[0][1]), ROOT / "code/ly/verify_route1_data_v2.py")
        self.assertEqual(Path(option(commands[0], "--data-root")), ENTRY.DATA)
        self.assertNotIn("--model-path", commands[0])
        self.assertNotIn("--adapter", commands[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
