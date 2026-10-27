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
                ? "V-Scheduler 模型目录暂时不可用，请稍后刷新，并检查 V-Scheduler 服务状态。"
                : "The V-Scheduler model catalog is temporarily unavailable. Retry shortly and check the V-Scheduler service status."
              : zh
              ? "模型与权限随当前 VOS 账户自动同步，无需填写服务地址或密钥。"
              : "Models and permissions sync automatically with your VOS account. No endpoint or API key is required."
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
