---
name: v-scheduler
description: 使用当前 VOS 用户的向量、图像/视频生成、语音合成/识别、结构化决策和 ML 模型；自动发现能力，无需填写密钥。
---

先调用 `scheduler_catalog`，按真实 `categories` 和 `endpoints` 选择模型，不根据名字猜测能力。模型 ID 必须使用目录中的完整 ID。

用 `scheduler_infer` 调用目录声明的推理接口：向量 `/v1/embeddings`；ASR `/v1/audio/transcriptions`；TTS `/v1/audio/speech`；图片 `/v1/images/generations`；视频 `/v1/videos/generations`；结构化决策 `/v1/systemone`；其他 ML `/v1/ml/predictions`。仅当目录实际提供相应接口时才调用。

音频/图片上传用 `file_path` 指定自己的工作区文件，其他参数放在 `body`。二进制响应必须指定工作区内的 `output_file`。普通 JSON 直接返回。异步接口返回任务并不代表生成完成，必须轮询实际结果；失败或无可用模型应明确说明。不要改用对话模型伪装向量、决策、语音或生成服务。

账户权限跟随当前 VOS 用户，代理只允许推理接口，不允许修改 Scheduler 的上游、模型登记或管理配置。不要索要 API Key 或管理员 token。
