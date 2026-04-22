# AI 业务分析助手（悬浮球）服务层
# - llm_client：通义千问（DashScope 兼容 OpenAI SDK）/ mock
# - tools：Function Calling 工具声明 + dispatcher（回调本地 insights_business）
# - prompt：System Prompt 与 data_card / report_content 契约
# - report：Markdown → .docx 转换
# - session：最近 10 轮会话历史（内存 TTLCache）
