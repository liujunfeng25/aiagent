# 对外汇报材料（Word / PPT / 图片）

面向**只使用 Word、PowerPoint、图片**的汇报场景；不含敏感连接信息。

## 文件清单

| 文件 | 说明 |
|------|------|
| **对外汇报-供应链数字化平台.docx** | Word 简版汇报稿，已嵌入架构图与两张示意图 |
| **对外汇报-供应链数字化平台.pptx** | 约 12 页演示片，含同款图片 |
| `platform-architecture-mindmap.png` | 分层架构意象图 |
| `对外汇报-只读洞察与平台关系图.png` | 业务只读与平台关系示意 |
| `对外汇报-AI训练推理闭环.png` | AI 闭环示意 |

## 重新生成 Word / PPT

在 `aiagent` 目录执行（需已安装 `python-docx`、`python-pptx`）：

```bash
python3 scripts/generate_external_briefing.py
```

## 使用建议

- 可将公司标准模板**复制样式**到本 Word，或把本文内容**粘贴进集团公文模板**。  
- PPT 可替换封面为集团 VI，并按需删减页数。  
- 详细技术版本仍见上级目录 Markdown，仅供研发与专利代理使用。
