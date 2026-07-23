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
import asyncio
from typing import List, Dict, Optional

from openai import AsyncOpenAI

from app.core.config import get_settings

settings = get_settings()


class KnowledgeExtractor:
    """
    知识提取器
    利用 DeepSeek API 从文本中自动提取知识点及其关系
    """

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )
        self.model = settings.DEEPSEEK_MODEL
        self.chunk_size = settings.CHUNK_SIZE
        self.chunk_overlap = settings.CHUNK_OVERLAP

    async def extract(self, text: str) -> Dict:
        """
        从文本中提取知识点和关系。

        Args:
            text: 待提取的文档文本

        Returns:
            {
                "knowledge_points": [
                    {"name": "知识点名称", "description": "描述", "order_index": 0},
                    ...
                ],
                "relations": [
                    {"source": "源知识点名称", "target": "目标知识点名称",
                     "relation_type": "prerequisite|related_to|part_of"},
                    ...
                ]
            }
        """
        # 将长文本分块处理
        chunks = self._chunk_text(text)
        all_kps: List[Dict] = []
        all_relations: List[Dict] = []

        for i, chunk in enumerate(chunks):
            chunk_result = await self._extract_from_chunk(chunk, offset=i * 100)

            if chunk_result.get("knowledge_points"):
                all_kps.extend(chunk_result["knowledge_points"])
            if chunk_result.get("relations"):
                all_relations.extend(chunk_result["relations"])

        # 去重：按知识点名称合并
        all_kps = self._deduplicate_kps(all_kps)
        all_relations = self._deduplicate_relations(all_relations, all_kps)

        return {
            "knowledge_points": all_kps,
            "relations": all_relations,
        }

    async def _extract_from_chunk(self, text: str, offset: int = 0) -> Dict:
        """从单个文本块中提取知识"""
        system_prompt = """你是一个教育领域的知识提取专家。你的任务是从给定的教学材料中提取知识点及其关系。

请严格按照以下JSON格式输出，不要输出任何其他内容：
{
  "knowledge_points": [
    {
      "name": "知识点名称（简洁准确）",
      "description": "知识点的简要描述（1-2句话）",
      "order_index": 0
    }
  ],
  "relations": [
    {
      "source": "源知识点名称（必须先学习的概念）",
      "target": "目标知识点名称（后学习的概念）",
      "relation_type": "prerequisite"
    }
  ]
}

提取规则：
1. 知识点应该是独立、可教学的概念或技能单元
2. 每个知识点要有明确的教学边界
3. relation_type 可选值：
   - "prerequisite": 源知识点是目标知识点的先修内容（学习顺序依赖）
   - "related_to": 两个知识点内容相关，可相互参考
   - "part_of": 源知识点是目标知识点的一个组成部分
4. order_index 表示知识点在原文中出现的大致顺序（从0开始递增）
5. 名称要简洁（不超过20字），描述要准确（不超过100字）"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",
                     "content": f"请从以下教学材料中提取知识点和关系：\n\n{text}"},
                ],
                temperature=0.3,
                max_tokens=4096,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
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
        将长文本切分为多个块，每块约为 chunk_size 个字符。
        保留 chunk_overlap 个字符的重叠区域以保持上下文。
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += (self.chunk_size - self.chunk_overlap)

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
