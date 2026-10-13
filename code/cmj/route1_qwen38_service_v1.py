"""
路线一 Qwen3.8 adapter 推理服务
支持加载底座 + 切换Sarol/SciCiteVal两个adapter
提供单条推理和批量推理接口
"""
import os, json, argparse, time
from typing import Optional, List, Dict

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

MODEL_PATH = r"C:\Users\Administrator\Documents\models\Qwen3.8-27B"

LABELS = ["ACCURATE", "NOT_ACCURATE", "IRRELEVANT"]


class Qwen38AdapterService:
    """Qwen3.8 adapter推理服务"""

    def __init__(self, model_path: str = MODEL_PATH, adapter_paths: Dict[str, str] = None,
                 load_in_4bit: bool = True):
        self.model_path = model_path
        self.adapter_paths = adapter_paths or {}
        self.current_adapter = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        print(f"[初始化] 模型: {model_path}")
        print(f"[初始化] 设备: {self.device}")
        if torch.cuda.is_available():
            print(f"[初始化] GPU: {torch.cuda.get_device_name(0)}, 显存: {torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB")

        # 加载tokenizer
        print("[初始化] 加载tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # 加载模型
        print("[初始化] 加载模型...")
        if load_in_4bit:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
            )
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16,
            )
        self.model.eval()
        self.base_model = self.model  # 保存底座引用

        # 预加载adapter（不激活）
        self.loaded_adapters = {}
        for name, path in self.adapter_paths.items():
            if os.path.exists(path):
                print(f"[初始化] 预加载adapter: {name} -> {path}")
                self.loaded_adapters[name] = path

        print("[初始化] 完成，当前为底座模式（M0）")

    def switch_adapter(self, adapter_name: Optional[str]):
        """切换adapter，None表示切回底座"""
        if adapter_name is None:
            if self.current_adapter is not None:
                print(f"[切换] 卸载adapter，回到底座模式")
                self.model = self.base_model
                self.current_adapter = None
            return

        if adapter_name not in self.loaded_adapters:
            raise ValueError(f"未找到adapter: {adapter_name}, 可用: {list(self.loaded_adapters.keys())}")

        if self.current_adapter == adapter_name:
            return

        print(f"[切换] 加载adapter: {adapter_name}")
        # 重新从底座加载adapter
        self.model = PeftModel.from_pretrained(self.base_model, self.loaded_adapters[adapter_name])
        self.model = self.model.merge_and_unload()
        self.model.eval()
        self.current_adapter = adapter_name
        print(f"[切换] 完成，当前adapter: {adapter_name}")

    def parse_label(self, text: str) -> str:
        """解析模型输出中的label"""
        text = text.strip()
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                obj = json.loads(text[start:end+1])
                label = obj.get("label", "").strip().upper()
                if label in LABELS:
                    return label
        except:
            pass
        for label in LABELS:
            if label in text.upper():
                return label
        return "INVALID"

    def predict(self, system_prompt: str, user_prompt: str,
                adapter_name: Optional[str] = None, max_new_tokens: int = 64) -> Dict:
        """单条推理"""
        if adapter_name is not None:
            self.switch_adapter(adapter_name)
        elif self.current_adapter is not None:
            self.switch_adapter(None)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=4096).to(self.device)

        start_time = time.time()
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        elapsed = time.time() - start_time

        generated = self.tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        label = self.parse_label(generated)

        return {
            "label": label,
            "raw_output": generated,
            "adapter": adapter_name or "M0",
            "inference_time_ms": round(elapsed * 1000, 1),
            "input_tokens": inputs["input_ids"].shape[1],
        }

    def batch_predict(self, records: List[Dict], adapter_name: Optional[str] = None,
                      max_new_tokens: int = 64) -> List[Dict]:
        """批量推理"""
        results = []
        for i, rec in enumerate(records):
            result = self.predict(
                system_prompt=rec["system_prompt"],
                user_prompt=rec["user_prompt"],
                adapter_name=adapter_name,
                max_new_tokens=max_new_tokens,
            )
            result["claim_id"] = rec.get("claim_id", i)
            result["gold"] = rec.get("gold", None)
            results.append(result)
            if (i+1) % 10 == 0:
                print(f"  [{i+1}/{len(records)}] 完成")
        return results

    def get_gpu_info(self) -> Dict:
        """获取GPU状态"""
        if not torch.cuda.is_available():
            return {"device": "cpu"}
        return {
            "device": self.device,
            "gpu_name": torch.cuda.get_device_name(0),
            "gpu_memory_total_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1),
            "gpu_memory_allocated_gb": round(torch.cuda.memory_allocated() / 1e9, 2),
            "gpu_memory_reserved_gb": round(torch.cuda.memory_reserved() / 1e9, 2),
            "current_adapter": self.current_adapter or "M0",
        }


def main():
    parser = argparse.ArgumentParser(description="Qwen3.8 adapter推理服务")
    parser.add_argument("--model_path", type=str, default=MODEL_PATH)
    parser.add_argument("--mbio_adapter", type=str, default=None, help="Sarol adapter路径")
    parser.add_argument("--mscv_adapter", type=str, default=None, help="SciCiteVal adapter路径")
    parser.add_argument("--demo", action="store_true", help="运行演示")
    args = parser.parse_args()

    adapter_paths = {}
    if args.mbio_adapter:
        adapter_paths["mbio"] = args.mbio_adapter
    if args.mscv_adapter:
        adapter_paths["mscv"] = args.mscv_adapter

    service = Qwen38AdapterService(
        model_path=args.model_path,
        adapter_paths=adapter_paths,
    )

    print("\nGPU状态:", json.dumps(service.get_gpu_info(), indent=2))

    if args.demo:
        print("\n=== 演示：底座M0推理 ===")
        result = service.predict(
            system_prompt="你是学术引文核验助手。标签：ACCURATE/NOT_ACCURATE/IRRELEVANT。输出JSON。",
            user_prompt="claim: 测试论断\n候选证据：D01:S01 | 测试证据",
            adapter_name=None,
        )
        print(f"结果: {result['label']}, 耗时: {result['inference_time_ms']}ms")

        if "mbio" in adapter_paths:
            print("\n=== 演示：Mbio(Sarol)推理 ===")
            result = service.predict(
                system_prompt="你是学术引文核验助手。",
                user_prompt="claim: 测试\n候选证据：D01:S01 | 测试",
                adapter_name="mbio",
            )
            print(f"结果: {result['label']}, 耗时: {result['inference_time_ms']}ms")

    print("\n服务就绪。使用 service.predict() 或 service.batch_predict() 进行推理。")


if __name__ == "__main__":
    main()
