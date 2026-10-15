"""CPU regression checks. No checkpoint download, PEFT, or GPU required.

Run with: python code/shared/route1_qwen38/test_data_contract.py
"""
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.route1_qwen38.data_contract import (
    AssistantOnlyCollator, compute_metrics, encode_assistant_record,
    load_gold, load_records, parse_label,
)


class ScoringTests(unittest.TestCase):
    def test_strict_label_parsing(self):
        cases = {
            "NOT_ACCURATE": "NOT_ACCURATE",
            '{"label":"NOT_ACCURATE"}': "NOT_ACCURATE",
            '```json\n{"label":"IRRELEVANT"}\n```': "IRRELEVANT",
            'Reason: NOT_ACCURATE': "INVALID",
            '{"label":"NOT_ACCURATE"} trailing prose': "INVALID",
            '{"label":"NOT_ACCURATE"': "INVALID",
            'ACCURATE NOT_ACCURATE': "INVALID",
            '{"label":"ACCURATE_NOT"}': "INVALID",
        }
        for raw, expected in cases.items():
            self.assertEqual(parse_label(raw), expected, raw)

    def test_invalid_is_false_negative(self):
        result = compute_metrics(
            ["ACCURATE", "INVALID", "NOT_ACCURATE", "IRRELEVANT"],
            ["ACCURATE", "ACCURATE", "NOT_ACCURATE", "IRRELEVANT"],
        )
        self.assertEqual(result["accuracy"], 0.75)
        self.assertEqual(result["per_class"]["ACCURATE"]["support"], 2)
        self.assertEqual(result["per_class"]["ACCURATE"]["fn"], 1)
        self.assertAlmostEqual(result["macro_f1"], 8 / 9)
        self.assertEqual(result["invalid_count"], 1)
        with self.assertRaises(ValueError):
            compute_metrics(["ACCURATE"], [])

    def test_id_join_and_legacy_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs, gold = root / "train.inputs.jsonl", root / "train.gold.jsonl"
            records = [
                {"claim_id": 12, "system_prompt": "s", "user_prompt": "u"},
                {"claim_id": "13", "system_prompt": "s", "user_prompt": "u"},
            ]
            inputs.write_text("".join(json.dumps(x) + "\n" for x in records), encoding="utf-8")
            gold.write_text('{"claim_id":"12","label":"ACCURATE"}\n{"claim_id":13,"label":"IRRELEVANT"}\n', encoding="utf-8")
            loaded = load_records(inputs, load_gold(gold), max_samples=1)
            self.assertEqual(loaded[0]["claim_id"], "12")
            self.assertEqual(loaded[0]["label"], "ACCURATE")
            legacy = root / "split.csv"
            legacy.write_text("row_id,project_label,split\n12,ACCURATE,train\n13,IRRELEVANT,dev\n", encoding="utf-8")
            self.assertEqual(load_gold(legacy, split="train"), {"12": "ACCURATE"})
            # A smoke cap must not hide a later missing/duplicate/bad join.
            with self.assertRaises(ValueError):
                load_records(inputs, {"12": "ACCURATE"}, max_samples=1)


class TorchBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        from tokenizers import Tokenizer, models, pre_tokenizers, trainers
        from transformers import PreTrainedTokenizerFast

        cls.torch = torch
        engine = Tokenizer(models.BPE(unk_token="[UNK]"))
        engine.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
        engine.train_from_iterator(
            ['system user evidence not labels', '{"label": "ACCURATE"}', '{"label": "NOT_ACCURATE"}', '{"label": "IRRELEVANT"}'],
            trainers.BpeTrainer(vocab_size=200, special_tokens=["[UNK]", "<|im_start|>", "<|im_end|>", "[PAD]"]),
        )
        cls.tokenizer = PreTrainedTokenizerFast(
            tokenizer_object=engine, unk_token="[UNK]", eos_token="<|im_end|>", pad_token="[PAD]"
        )
        cls.tokenizer.chat_template = (
            "{% if enable_thinking != false %}{{ raise_exception('thinking must be explicitly false') }}{% endif %}"
            "{% for message in messages %}{{ '<|im_start|>' + message['role'] + '\\n' + message['content'] + '<|im_end|>\\n' }}{% endfor %}"
        )

    def test_real_fast_tokenization_padding_and_loss(self):
        records = [
            {"claim_id": "external-only-12", "label": "ACCURATE", "system_prompt": "system", "user_prompt": "evidence"},
            {"claim_id": "external-only-13", "label": "NOT_ACCURATE", "system_prompt": "system", "user_prompt": "evidence " * 10},
        ]
        features = [encode_assistant_record(row, self.tokenizer, 512) for row in records]
        for feature in features:
            self.assertTrue(any(x == -100 for x in feature["labels"]))
            tokens = [token for token in feature["labels"] if token != -100]
            decoded = self.tokenizer.decode(tokens)
            self.assertIn('label', decoded)
            self.assertNotIn('system', decoded)
            self.assertNotIn('evidence', decoded)
        for side in ("left", "right"):
            self.tokenizer.padding_side = side
            batch = AssistantOnlyCollator(self.tokenizer)(features)
            self.assertTrue(self.torch.all(batch["labels"][batch["attention_mask"] == 0] == -100))
            for index, feature in enumerate(features):
                attended = batch["attention_mask"][index].bool()
                self.assertEqual(batch["labels"][index][attended].tolist(), feature["labels"])
            # Real CPU cross entropy: masked prompt/padding positions have zero gradient.
            logits = self.torch.randn(*batch["labels"].shape, len(self.tokenizer), requires_grad=True)
            loss = self.torch.nn.functional.cross_entropy(
                logits[:, :-1].reshape(-1, len(self.tokenizer)), batch["labels"][:, 1:].reshape(-1), ignore_index=-100
            )
            self.assertTrue(math.isfinite(loss.item()))
            loss.backward()
            ignored = batch["labels"][:, 1:] == -100
            self.assertTrue(self.torch.all(logits.grad[:, :-1][ignored] == 0))
            self.assertGreater(logits.grad.abs().sum().item(), 0)
        # Qwen commonly reuses EOS for padding. Preserve the real EOS label;
        # only newly inserted padding positions receive -100.
        original_pad = self.tokenizer.pad_token
        self.tokenizer.pad_token = self.tokenizer.eos_token
        batch = AssistantOnlyCollator(self.tokenizer)(features)
        for index, feature in enumerate(features):
            active = batch["attention_mask"][index].bool()
            self.assertEqual(batch["labels"][index][active].tolist(), feature["labels"])
        self.tokenizer.pad_token = original_pad
        with self.assertRaises(ValueError):
            encode_assistant_record(records[0], self.tokenizer, 2)

    def test_check_inputs_cli_processes_full_split_without_weights(self):
        repo = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model_dir = root / "tokenizer_only"
            self.tokenizer.save_pretrained(model_dir)
            (model_dir / "config.json").write_text('{"model_type":"qwen2"}', encoding="utf-8")
            inputs, gold = root / "train.inputs.jsonl", root / "train.gold.jsonl"
            rows = [{"claim_id": str(index), "system_prompt": "system", "user_prompt": "evidence"} for index in range(35)]
            inputs.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            gold.write_text("".join(json.dumps({"claim_id": row["claim_id"], "label": "ACCURATE"}) + "\n" for row in rows), encoding="utf-8")
            for script in ("code/cmj/route1_qwen38_train_sarol_v1.py", "code/ly/route1_qwen38_train_sciciteval_v1.py"):
                result = subprocess.run(
                    [sys.executable, str(repo / script), "--model-path", str(model_dir),
                     "--inputs", str(inputs), "--gold", str(gold),
                     "--output-dir", str(root / Path(script).stem), "--check-inputs"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("check_inputs_ok=true records=35", result.stdout)
                self.assertIn("GPU model loading/training NOT performed", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
