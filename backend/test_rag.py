"""
RAG 对话测试脚本
---------------
独立测试 DeepSeek + LangChain 链路，不依赖 Neo4j。

用法:
    cd backend
    # 先在 .env 里填好 DEEPSEEK_API_KEY
    python test_rag.py
"""

import sys
import asyncio

print("=" * 60)
print("1. Checking environment variables...")

from app.core.config import get_settings
settings = get_settings()

api_key = settings.DEEPSEEK_API_KEY
if not api_key or api_key == "sk-your-api-key":
    print("[FAIL] Please set DEEPSEEK_API_KEY in backend/.env")
    sys.exit(1)

print(f"[OK] API Key configured: {api_key[:8]}...")
print(f"     Model: {settings.DEEPSEEK_MODEL}")
print(f"     Base URL: {settings.DEEPSEEK_BASE_URL}")

# ---- Test DeepSeek API ----
print("\n" + "=" * 60)
print("2. Testing DeepSeek API...")

async def test_direct_api():
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
    )

    try:
        resp = await client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": "你好，请用一句话介绍你自己。"}],
            max_tokens=100,
        )
        text = resp.choices[0].message.content
        print(f"[OK] DeepSeek API works!")
        print(f"    Reply: {text}")
        return True
    except Exception as e:
        print(f"[FAIL] DeepSeek API error: {e}")
        return False

# ---- Test LangChain ----
print("\n" + "=" * 60)
print("3. Testing LangChain + DeepSeek chain...")

async def test_langchain():
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    try:
        llm = ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0.7,
            max_tokens=500,
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个课程AI助教。请基于参考内容回答。\n\n参考内容：\n{context}"),
            ("user", "{question}"),
        ])

        chain = prompt | llm | StrOutputParser()

        context = """知识点1：傅里叶变换
内容：将时域信号转换为频域表示的积分变换，适用于稳态信号分析。

知识点2：拉普拉斯变换
内容：引入衰减因子的广义傅里叶变换，适用于系统传递函数分析和微分方程求解。"""

        question = "傅里叶变换和拉普拉斯变换有什么区别？"

        answer = await chain.ainvoke({
            "context": context,
            "question": question,
        })

        print("[OK] LangChain chain works!")
        print(f"    Question: {question}")
        print(f"    Answer: {answer}")
        return True
    except Exception as e:
        print(f"[FAIL] LangChain error: {e}")
        import traceback
        traceback.print_exc()
        return False

# ---- Run all ----
async def main():
    results = []
    results.append(await test_direct_api())
    results.append(await test_langchain())

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  DeepSeek API:    {'PASS' if results[0] else 'FAIL'}")
    print(f"  LangChain:       {'PASS' if results[1] else 'FAIL'}")
    print()

    if results[0] and results[1]:
        print("Core RAG pipeline ready! Just need Neo4j for full retrieval.")
    else:
        print("Check your DEEPSEEK_API_KEY and account balance.")

asyncio.run(main())
