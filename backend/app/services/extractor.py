"""
知识提取服务
------------
使用 DeepSeek 大语言模型从文档文本中自动提取：
1. 知识点（Knowledge Points）— 名称、描述
2. 知识点之间的关系（Relations）— 先修关系、相关关系、组成关系

工作流程：
    文档文本 → 分块 → DeepSeek API 提取 → 结构化输出

技术栈：
- OpenAI SDK（兼容 DeepSeek API）
- jieba 中文分词

使用方式：
    from app.services.extractor import KnowledgeExtractor
    extractor = KnowledgeExtractor()
    result = await extractor.extract(text)
"""

import json
import re
import asyncio
from typing import List, Dict, Optional
from functools import partial

import jieba
import requests

from app.core.config import get_settings

settings = get_settings()


class KnowledgeExtractor:
    """知识提取器 — 使用 requests 直连 DeepSeek API"""

    def __init__(self):
        self._ready = bool(settings.DEEPSEEK_API_KEY and
                          settings.DEEPSEEK_API_KEY not in ("your-deepseek-api-key", ""))
        self.api_key = settings.DEEPSEEK_API_KEY
        self.base_url = settings.DEEPSEEK_BASE_URL.rstrip("/")
        self.model = settings.DEEPSEEK_MODEL
        self.chunk_size = settings.CHUNK_SIZE
        self.chunk_overlap = settings.CHUNK_OVERLAP

    async def extract(self, text: str) -> Dict:
        """从文本中提取三层树状知识结构。"""
        if not self._ready:
            print("[Extractor] DeepSeek API Key 未配置，跳过提取")
            return {"modules": [], "knowledge_points": [], "relations": []}

        chunks = self._chunk_text(text)
        all_modules: List[Dict] = []
        all_kps: List[Dict] = []
        all_relations: List[Dict] = []

        tasks = [self._extract_from_chunk(chunk, offset=i * 100) for i, chunk in enumerate(chunks)]
        chunk_results = await asyncio.gather(*tasks)

        for chunk_result in chunk_results:
            if chunk_result.get("modules"):
                all_modules.extend(chunk_result["modules"])
            if chunk_result.get("knowledge_points"):
                all_kps.extend(chunk_result["knowledge_points"])
            if chunk_result.get("relations"):
                all_relations.extend(chunk_result["relations"])

        # 合并模块
        all_modules = self._deduplicate_modules(all_modules)
        # 从树结构展平知识点
        flat_kps = self._flatten_modules(all_modules)
        if flat_kps:
            all_kps = flat_kps

        all_relations = self._deduplicate_relations(all_relations, all_kps)

        return {
            "modules": all_modules,
            "knowledge_points": all_kps,
            "relations": all_relations,
        }

    def _flatten_modules(self, modules: List[Dict]) -> List[Dict]:
        """将树状模块展平为知识点列表，保留层级标记"""
        flat = []
        for mod in modules:
            flat.append({"name": mod["name"], "description": mod.get("description", ""),
                         "order_index": mod.get("order_index", 0), "level": 0, "is_module": True})
            for sub in mod.get("sub_modules", []):
                flat.append({"name": sub["name"], "description": sub.get("description", ""),
                             "order_index": sub.get("order_index", 0), "level": 1, "is_module": True,
                             "parent_name": mod["name"]})
                for kp in sub.get("knowledge_points", []):
                    flat.append({"name": kp["name"], "description": kp.get("description", ""),
                                 "order_index": kp.get("order_index", 0), "level": 2, "is_module": False,
                                 "parent_name": sub["name"]})
        return flat

    def _deduplicate_modules(self, modules: List[Dict]) -> List[Dict]:
        """按模块名去重，合并子模块和知识点"""
        seen = {}
        for mod in modules:
            name = mod["name"].strip()
            if name in seen:
                existing_subs = {s["name"]: s for s in seen[name].get("sub_modules", [])}
                for sub in mod.get("sub_modules", []):
                    if sub["name"] not in existing_subs:
                        seen[name].setdefault("sub_modules", []).append(sub)
                    else:
                        ekps = {k["name"] for k in existing_subs[sub["name"]].get("knowledge_points", [])}
                        for kp in sub.get("knowledge_points", []):
                            if kp["name"] not in ekps:
                                existing_subs[sub["name"]].setdefault("knowledge_points", []).append(kp)
            else:
                seen[name] = mod
        result = list(seen.values())
        result.sort(key=lambda x: x.get("order_index", 0))
        return result

    async def _extract_from_chunk(self, text: str, offset: int = 0) -> Dict:
        """从单个文本块中提取知识"""
        system_prompt = """你是一个教育领域的知识提取专家。从教学材料中提取**三层树状**知识结构。

请严格按以下JSON格式输出：
{
  "modules": [
    {
      "name": "知识模块名称（如'Python基础'）",
      "description": "模块概述",
      "order_index": 0,
      "sub_modules": [
        {
          "name": "子模块名称（如'变量与数据类型'）",
          "description": "子模块描述",
          "order_index": 0,
          "knowledge_points": [
            {"name": "具体知识点", "description": "解释", "order_index": 0}
          ]
        }
      ]
    }
  ],
  "relations": [
    {
      "source": "源模块或知识点名",
      "target": "目标模块或知识点名",
      "relation_type": "prerequisite"
    }
  ]
}

提取规则（重要！请严格遵循，否则生成的图谱会过于复杂）：
1. **三层结构**：模块(大章) → 子模块(小节) → 知识点(具体概念)
2. **粒度控制**：
   - 每个模块含 2~4 个子模块
   - 每个子模块含 2~5 个知识点
   - 知识点应是可独立教学的最小单元
   - **不要**拆分得太细！合并相近概念
3. **⭐ 关系规则（核心！违反此条会导致图谱混乱）**：
   - "prerequisite"：**只能**用于模块与模块之间（如"Python基础"→"控制流程"）
   - **禁止**在知识点之间、子模块之间加 prerequisite 边！
   - **每个课程最多 3~5 条 prerequisite 关系**
   - "related_to"：**忽略不写**（不重要）
   - 子模块与其模块之间**不需要**写关系
4. 名称≤15字，描述≤80字
5. modules 数组内最多包含一个对象，把所有模块都写在这一个对象里"""

        try:
            # 使用 requests 直连（避免 httpx SSL 问题）
            resp = await asyncio.get_event_loop().run_in_executor(
                None,
                partial(
                    requests.post,
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"请从以下教学材料中提取知识点和关系：\n\n{text}"},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 4096,
                        "response_format": {"type": "json_object"},
                    },
                    timeout=120,
                    proxies={"http": None, "https": None},  # 禁用系统代理
                )
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)

            # 为每个知识点的 order_index 加上偏移量
            if result.get("knowledge_points"):
                for kp in result["knowledge_points"]:
                    kp["order_index"] = kp.get("order_index", 0) + offset

            return result

        except json.JSONDecodeError:
            return {"knowledge_points": [], "relations": []}
        except Exception as e:
            print(f"[Extractor] 提取失败: {e}")
            return {"knowledge_points": [], "relations": []}

    def _chunk_text(self, text: str) -> List[str]:
        """
        将长文本切分为多个块，使用 jieba 分词在句子边界处切割，
        避免在中文字词中间断开，保持语义完整性。

        每块约为 chunk_size 个字符，保留 chunk_overlap 个字符重叠。
        """
        if len(text) <= self.chunk_size:
            return [text]

        # 使用 jieba 分词识别词语边界
        words = list(jieba.cut(text))

        chunks = []
        current_chunk = []
        current_len = 0
        overlap_buffer = []

        for word in words:
            word_len = len(word)
            current_chunk.append(word)
            current_len += word_len

            if current_len >= self.chunk_size:
                chunk_text = "".join(current_chunk)
                chunks.append(chunk_text)

                # 保留末尾 overlap 长度的词语作为下一块的上下文
                overlap_chars = 0
                overlap_buffer = []
                for w in reversed(current_chunk):
                    overlap_chars += len(w)
                    overlap_buffer.insert(0, w)
                    if overlap_chars >= self.chunk_overlap:
                        break

                current_chunk = list(overlap_buffer)
                current_len = sum(len(w) for w in current_chunk)

        # 处理最后一块
        if current_chunk:
            remaining = "".join(current_chunk)
            if remaining not in chunks:
                chunks.append(remaining)

        return chunks

    def _deduplicate_kps(self, kps: List[Dict]) -> List[Dict]:
        """按名称去重知识点，合并描述"""
        seen = {}
        for kp in kps:
            name = kp["name"].strip()
            if name in seen:
                # 保留较长的描述
                if len(kp.get("description", "")) > len(
                        seen[name].get("description", "")):
                    seen[name]["description"] = kp["description"]
            else:
                seen[name] = kp

        # 重新分配 order_index
        result = list(seen.values())
        result.sort(key=lambda x: x.get("order_index", 0))
        for i, kp in enumerate(result):
            kp["order_index"] = i

        return result

    def _deduplicate_relations(
            self,
            relations: List[Dict],
            kps: List[Dict]
    ) -> List[Dict]:
        """去重关系"""
        kp_names = {kp["name"] for kp in kps}
        seen = set()
        unique_relations = []

        for rel in relations:
            source = rel.get("source", "").strip()
            target = rel.get("target", "").strip()
            rtype = rel.get("relation_type", "related_to")

            # 验证知识点名称存在
            if source not in kp_names or target not in kp_names:
                continue
            if source == target:
                continue

            key = (source, target, rtype)
            if key not in seen:
                seen.add(key)
                unique_relations.append({
                    "source": source,
                    "target": target,
                    "relation_type": rtype,
                })

        return unique_relations


# 便捷函数
async def extract_knowledge(text: str) -> Dict:
    """从文本提取知识的便捷函数"""
    extractor = KnowledgeExtractor()
    return await extractor.extract(text)
