---
name: photocraft
description: 使用当前 VOS 用户的 PhotoCraft 编辑图片、操作图层和选区、调色、预览并导出 PNG/PSD；无需再次登录。
---

# PhotoCraft

先调用 `photocraft_catalog` 读取当前服务实际提供的工具及参数，再用 `photocraft_call` 调用原生 MCP 工具。工具名和参数必须来自目录，不能猜测。工作区、文件权限和认证绑定当前 VOS 用户；不要索要 token。

遵循「探、改、验」：先检查文档/命令参数；按用户要求执行一组编辑；通过预览和图层状态检查结果；显式导出交付文件。保持同一个 MCP 会话，使连续调用操作同一份文档。打开另一张图片会改变活动文档。

只读写用户明确指定的图片和输出。路径来自当前用户获准的 VOS 目录；需要查询目录或传输文件时，可用 `vos_api` 的 `photocraft` 服务访问 `/volumes`、`/index`、`/download`、`/upload`。

用户提供的矩形坐标按其声明的单位和原始边界使用，不扩大范围，不凭空创造选区。局部处理应先建选区或蒙版，再执行调整，最后预览验证。不要把整图处理宣称为局部处理。

原生服务提供文档、命令、预览和导出工具，不提供桌面窗口控制或生成式修图。生成和补绘使用 V-Scheduler/Image Studio；PhotoCraft 用于像素、图层和选区编辑。服务不可用时明确报告，不能虚构编辑或产物。

实现参考 v-harness 0.1.12 的 PhotoCraft 用户能力代理，以及 PhotoCraft 的 `docs/vos-integration.md`；工具直接来自 PhotoCraft MCP，而非 v-harness 专用插件。
