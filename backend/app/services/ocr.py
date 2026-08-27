"""
OCR 文档识别服务 (功能4)
------------------------
封装 RapidOCR（onnxruntime 版，中文识别效果好、离线、纯 pip 安装），
支持扫描件 PDF 与图片的文字识别，并接入知识提取流水线。

说明：
  - OCR 引擎为可选依赖：未安装时优雅降级，返回空字符串，由调用方回退。
  - 安装：pip install rapidocr_onnxruntime
  - 首次实例化会自动下载 det/rec/cls 模型（约数十 MB，缓存在本地）。

使用方式：
    from app.services.ocr import get_ocr_service
    text = get_ocr_service().extract_image("path/to/image.png")
"""

from typing import List, Optional


class OCRService:
    """OCR 识别服务（懒加载 RapidOCR 引擎）。"""

    def __init__(self):
        self._ocr = None
        self._init_attempted = False
        self._error: Optional[str] = None

    def is_available(self) -> bool:
        """检测 OCR 引擎是否可用（幂等，懒加载）。"""
        if self._init_attempted:
            return self._ocr is not None
        self._init_attempted = True
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr = RapidOCR()
            return True
        except Exception as e:  # noqa: BLE001
            self._error = str(e)
            return False

    def extract_image(self, file_path: str) -> str:
        """识别单张图片中的文字。"""
        if not self.is_available():
            return ""
        try:
            result, _ = self._ocr(file_path)
            return self._join_result(result)
        except Exception as e:  # noqa: BLE001
            self._error = str(e)
            return ""

    def extract_pdf(self, file_path: str) -> str:
        """
        识别扫描版 PDF（无嵌入文字层）。

        通过 PyMuPDF(fitz) 将每页渲染为图片后逐页 OCR，无需 poppler。
        """
        if not self.is_available():
            return ""
        try:
            import fitz
            import numpy as np
        except Exception as e:  # noqa: BLE001
            self._error = f"缺少依赖（pip install pymupdf）: {e}"
            return ""

        try:
            doc = fitz.open(file_path)
        except Exception as e:  # noqa: BLE001
            self._error = f"PDF 打开失败: {e}"
            return ""

        parts: List[str] = []
        try:
            for page in doc:
                try:
                    pix = page.get_pixmap(dpi=200)
                    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                        pix.height, pix.width, pix.n)
                    if pix.n == 4:  # RGBA → RGB
                        img = img[:, :, :3]
                    result, _ = self._ocr(img)
                    parts.append(self._join_result(result))
                except Exception:  # noqa: BLE001
                    continue
        finally:
            doc.close()
        return "\n\n".join(p for p in parts if p)

    @staticmethod
    def _join_result(result) -> str:
        """将 RapidOCR 结果拼接为文本。"""
        if not result:
            return ""
        lines: List[str] = []
        for item in result:
            if item and len(item) >= 2 and item[1]:
                lines.append(str(item[1]))
        return "\n".join(lines)


# 单例
_ocr_service: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service


def is_scanned_pdf(extracted_text: str, page_count: int) -> bool:
    """判断 PDF 是否为扫描版：有页数但提取到的文字极少。"""
    if page_count <= 0:
        return False
    meaningful = len("".join(extracted_text.split()))
    return meaningful < 20
