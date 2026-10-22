"""Explicit A100 backend for the PDF v3 prototype. Importing never loads weights."""
from __future__ import annotations

from collections import Counter
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess

import route1_pdf_pipeline_v3 as contract
import prepare_pdf20_scope_inputs_20261020 as preparation

# SHA of the official 18-shard list already checked during the A100 handoff.
OFFICIAL_SUMS_SHA = "3ebc83ee545cc54cb2558d805802d4a4e9da42c316d1b248846debee545b99c9"
ADAPTER_CONFIG_SHA = "b425bcd6ba101d02dcb1dd8d9f892b315bd082a7b6feeba938b43bc58aedc2f8"


def verify_weight_files(model_path, manifest):
    model_path, manifest = Path(model_path), Path(manifest)
    contract.require(contract.sha(manifest) == OFFICIAL_SUMS_SHA, "Official 18-shard hash list differs from the archived A100 verification")
    expected = {}
    for line in manifest.read_text(encoding="utf-8-sig").splitlines():
        match = re.fullmatch(r"([a-f0-9]{64})\s+\*?(model-\d{5}-of-00018\.safetensors)", line.strip())
        contract.require(match is not None and match[2] not in expected, "Malformed or repeated shard in official list")
        expected[match[2]] = match[1]
    contract.require(set(expected) == {f"model-{i:05d}-of-00018.safetensors" for i in range(1, 19)}, "Incomplete official weight list")
    index = contract.read_json(model_path / "model.safetensors.index.json")
    contract.require(set(index["weight_map"].values()) == set(expected), "Index references different shards")
    for filename, digest in expected.items():
        actual = contract.sha(model_path / filename)
        contract.require(actual == digest, f"Official weight shard hash mismatch: {filename}")
        print(filename, "SHA256_OK", flush=True)
    return {"official_sums_sha256": OFFICIAL_SUMS_SHA, "shards_sha256": expected,
            "weight_index_sha256": contract.sha(model_path / "model.safetensors.index.json")}


class HFBackend:
    def __init__(self, stage, plan, model_path, adapter, weights_manifest, gpu, operator):
        contract.require(stage in ("classifier", "explainer") and re.fullmatch(r"\d+", gpu) is not None, "Select one physical GPU index")
        contract.require(plan["settings"] == {"max_length": 5120, "max_new_tokens": 512, "enable_thinking": False,
                                            "do_sample": False, "retry_policy": "none; keep all first attempts"}, "Runtime settings drift")
        model_path = Path(model_path)
        for filename, expected in preparation.TOKENIZER_FILES.items():
            contract.require(contract.sha(model_path / filename) == expected, f"Official base/tokenizer mismatch: {filename}")
        weight_proof = verify_weight_files(model_path, weights_manifest)
        adapter_hash = adapter_config_hash = None
        if stage == "classifier":
            contract.require(adapter is not None, "Classifier must load the preselected Mbio checkpoint-100")
            adapter_hash = contract.sha(Path(adapter) / "adapter_model.safetensors")
            adapter_config_hash = contract.sha(Path(adapter) / "adapter_config.json")
            contract.require(adapter_hash == contract.ADAPTER_SHA and adapter_config_hash == ADAPTER_CONFIG_SHA, "Preselected adapter/config mismatch")
        else:
            contract.require(adapter is None, "Independent official-base explainer must not load an adapter")
        # This backend is only reached by an explicit run-* command. Never used by CPU preparation.
        os.environ.update(CUDA_VISIBLE_DEVICES=gpu, TOKENIZERS_PARALLELISM="false", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        contract.require(importlib.metadata.version("transformers") == "5.8.0", "Frozen runtime requires transformers 5.8.0")
        contract.require(torch.cuda.is_available() and torch.cuda.device_count() == 1, "Exactly one selected CUDA GPU required")
        free, total = torch.cuda.mem_get_info(0)
        contract.require(free // (1024 * 1024) >= 30000, "Less than 30000 MiB free; stop before model loading")
        allocator_budget = free - 2048 * (1024 * 1024)
        contract.require(0 < allocator_budget < total, "Invalid PyTorch allocator budget")
        torch.cuda.set_per_process_memory_fraction(allocator_budget / total, device=0)
        torch.cuda.reset_peak_memory_stats(0)
        self.resource_budget = {
            "execution_revision": "route1_pdf_first5_resource_v1_20261022",
            "min_free_MiB": 30000, "headroom_MiB": 2048,
            "pytorch_allocator_budget_bytes": allocator_budget,
            "pytorch_allocator_fraction": allocator_budget / total,
            "external_CUDA_allocations_not_fully_capped": True,
            "memory_preflight_not_exact_generation_guarantee": True,
        }
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16,
                                   bnb_4bit_use_double_quant=False)
        self.model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True, trust_remote_code=False,
                                                         quantization_config=quant, device_map={"": 0})
        if adapter is not None:
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, adapter, local_files_only=True)
        self.model.eval()
        placement = Counter(str(p.device) for p in self.model.parameters())
        contract.require(placement and all(device.startswith("cuda:") for device in placement), "CPU/disk model offload is not this configured GPU run")
        lora = [n for n, m in self.model.named_modules() if hasattr(m, "lora_A") or hasattr(m, "lora_B")]
        contract.require(bool(lora) == (stage == "classifier"), "Loaded adapter role mismatch")
        inventory = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid,name,memory.used,memory.free,utilization.gpu", "--format=csv,noheader"],
                                   capture_output=True, text=True, timeout=20)
        contract.require(inventory.returncode == 0, "GPU inventory logging failed")
        self.identity = {"role": stage, "base": "Qwen/Qwen3.8-27B", "revision": preparation.BASE_REVISION,
                         "model_path": str(model_path), "base_files_sha256": preparation.TOKENIZER_FILES, **weight_proof,
                         "adapter_path": str(adapter) if adapter else None, "adapter_sha256": adapter_hash,
                         "adapter_config_sha256": adapter_config_hash, "adapter_loaded": bool(lora),
                         "model_class": type(self.model).__name__, "parameter_tensor_placement": dict(placement),
                         "physical_gpu": gpu, "gpu_name": torch.cuda.get_device_name(0), "gpu_inventory": inventory.stdout,
                         "gpu_free_before_load_bytes": free, "gpu_total_bytes": total,
                         "gpu_allocated_after_load_bytes": torch.cuda.memory_allocated(0),
                         "gpu_loaded": True, "weights_verified": True, "simulation": False,
                         "quantization": quant.to_dict(), "operator": operator, "python": platform.python_version(),
                         "versions": {n: importlib.metadata.version(n) for n in ("torch", "transformers", "peft", "accelerate", "bitsandbytes")},
                         "CUDA_VISIBLE_DEVICES": gpu, "enable_thinking": False, "do_sample": False}

    def generate(self, record, expected):
        observed = contract.budget(self.tokenizer, record)
        contract.require(observed["within_budget"] and observed["input_ids_sha256"] == expected["input_ids_sha256"]
                         and observed["input_tokens"] == expected["input_tokens"], "Actual tokenizer differs from released CPU budget")
        text = self.tokenizer.apply_chat_template([{"role": "system", "content": record["system_prompt"]},
                                                  {"role": "user", "content": record["user_prompt"]}],
                                                 tokenize=False, add_generation_prompt=True, enable_thinking=False)
        encoded = self.tokenizer(text, add_special_tokens=False, truncation=False, return_tensors="pt").to(self.model.get_input_embeddings().weight.device)
        self.torch.cuda.synchronize(0)
        with self.torch.inference_mode():
            generated = self.model.generate(**encoded, max_new_tokens=512, do_sample=False, pad_token_id=self.tokenizer.pad_token_id)
        self.torch.cuda.synchronize(0)
        raw = self.tokenizer.decode(generated[0][observed["input_tokens"]:], skip_special_tokens=True)
        observed["generated_token_ids"] = generated[0][observed["input_tokens"]:].tolist()
        observed["generated_tokens"] = len(observed["generated_token_ids"])
        observed["peak_GPU_allocated_bytes"] = self.torch.cuda.max_memory_allocated(0)
        return raw, observed
