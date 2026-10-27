import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Empty, Space, Tag, Typography } from "antd";
import { useTranslation } from "react-i18next";
type Model = {
  id: string;
  name: string;
  endpoints: string[];
  categories: string[];
  input?: string[];
};
export default function VosModelCatalog({ category }: { category: string }) {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    try {
      const r = await fetch(`${import.meta.env.BASE_URL}__va/model-catalog`, {
        credentials: "same-origin",
      });
      if (!r.ok) throw new Error();
      const data = await r.json();
      setModels(data.models);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  const visible = models.filter((row) => row.categories.includes(category));
  return (
    <Card
      loading={loading}
      title="V-Scheduler"
      extra={
        <Button onClick={() => void load()}>{zh ? "刷新" : "Refresh"}</Button>
      }
    >
      <Space direction="vertical" style={{ width: "100%" }}>
        <Alert
          type={failed ? "error" : "info"}
          showIcon
          message={
            failed
              ? zh
                ? "无法读取当前用户的模型目录，请刷新 VOS 登录后重试。"
                : "Could not load your model catalog. Refresh the VOS session and retry."
              : zh
              ? "模型与权限来自当前 VOS 用户，无需填写服务地址或密钥。生成和决策通过已安装的 V-Scheduler MCP 工具调用；语音和向量服务自动同步到对应配置。"
              : "Models and permissions follow your VOS account. No endpoint or API key is needed. Generation and decisions use the installed V-Scheduler MCP tools; voice and embedding providers sync automatically."
          }
        />
        {!failed && !visible.length && (
          <Empty
            description={
              zh
                ? "V-Scheduler 当前没有向你提供该分类的接口；不会把对话模型当作此类服务。"
                : "V-Scheduler currently exposes no service in this category for your account."
            }
          />
        )}
        {visible.map((model) => (
          <Card key={model.id} size="small">
            <Typography.Text strong>{model.name}</Typography.Text>
            <div>
              <Typography.Text type="secondary">{model.id}</Typography.Text>
            </div>
            <Space wrap>
              {model.endpoints.map((path) => (
                <Tag key={path}>{path}</Tag>
              ))}
            </Space>
          </Card>
        ))}
      </Space>
    </Card>
  );
}
