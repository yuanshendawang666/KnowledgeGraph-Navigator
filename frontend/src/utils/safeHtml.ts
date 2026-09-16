import DOMPurify from 'dompurify'

// 统一出口：Markdown 结果与富文本都在插入 DOM 前清洗。
export function safeHTML(value: string): string {
  return DOMPurify.sanitize(value, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['style', 'form', 'input', 'button', 'iframe', 'object', 'embed'],
    FORBID_ATTR: ['srcdoc'],
  })
}
