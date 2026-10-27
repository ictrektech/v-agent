import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  InputNumber,
  Select,
  Space,
  Spin,
  Switch,
} from "antd";
import { useTranslation } from "react-i18next";
import { message } from "@/utils/antdMessage";
import {
  decisionApi,
  type DecisionSettings,
} from "../../../../api/modules/decision";

type Model = { id: string; name: string; endpoints: string[] };

/** Native decision filtering, routed through the current user's Scheduler. */
export default function VosDecisionSettingsPanel() {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<DecisionSettings>();
  const [models, setModels] = useState<Model[]>([]);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    void Promise.all([
      decisionApi.get(),
      fetch(`${import.meta.env.BASE_URL}__va/model-catalog`, {
        credentials: "same-origin",
      }).then(async (r) => {
        if (!r.ok) throw new Error("Model catalog unavailable");
        return r.json() as Promise<{ models: Model[] }>;
      }),
    ])
      .then(([saved, catalog]) => {
        if (!active) return;
        setSettings(saved);
        setModels(
          catalog.models.filter((model) =>
            model.endpoints.includes("systemone"),
          ),
        );
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);
  const patch = (change: Partial<DecisionSettings>) =>
    setSettings((saved) => saved && { ...saved, ...change });
  const save = async () => {
    if (!settings) return;
    setBusy(true);
    try {
      setSettings(
        await decisionApi.save({
          enabled: settings.enabled,
          provider: "jev",
          endpoint: settings.endpoint,
          model: settings.model,
          skills: settings.skills,
          tools: settings.tools,
          team: settings.team,
          threshold: settings.threshold,
          tool_min_count: settings.tool_min_count,
        }),
      );
      message.success(t("voice.saved"));
    } catch {
      message.error(t("common.saveFailed"));
    } finally {
      setBusy(false);
    }
  };
  const probe = async () => {
    setBusy(true);
    try {
      const result = await decisionApi.test({
        model: settings?.model,
        provider: "jev",
      });
      if (result.ok) message.success(t("voice.probeSuccess"));
      else message.error(result.error || t("voice.probeFailed"));
    } catch {
      message.error(t("voice.probeFailed"));
    } finally {
      setBusy(false);
    }
  };
  if (failed)
    return <Alert type="error" message={t("models.decisionLoadFailed")} />;
  if (!settings) return <Spin />;
  return (
    <Card title="V-Scheduler / Jev · System One">
      <Space direction="vertical" style={{ width: "100%" }}>
        <p>{t("models.decisionIntro")}</p>
        <Space>
          <Switch
            checked={settings.enabled}
            onChange={(enabled) => patch({ enabled })}
            disabled={!models.length}
          />
          {t("models.decisionEnabled")}
        </Space>
        <Select
          style={{ width: "100%" }}
          aria-label={t("models.decisionModel")}
          value={settings.model || undefined}
          placeholder={t("models.decisionModel")}
          options={models.map((model) => ({
            value: model.id,
            label: model.name,
          }))}
          onChange={(model) => patch({ model })}
        />
        {!models.length && (
          <Alert type="info" message={t("voice.vosNoDecision")} />
        )}
        {(["skills", "tools", "team"] as const).map((key) => (
          <Checkbox
            key={key}
            checked={settings[key]}
            onChange={(event) => patch({ [key]: event.target.checked })}
          >
            {t(`models.decision${key[0].toUpperCase()}${key.slice(1)}`)}
          </Checkbox>
        ))}
        <Space>
          {t("models.decisionThreshold")}
          <InputNumber
            min={0}
            max={1}
            step={0.05}
            value={settings.threshold}
            onChange={(threshold) => threshold !== null && patch({ threshold })}
          />
        </Space>
        <Space>
          {t("models.decisionToolMin")}
          <InputNumber
            min={0}
            value={settings.tool_min_count}
            onChange={(tool_min_count) =>
              tool_min_count !== null && patch({ tool_min_count })
            }
          />
        </Space>
        <Space>
          <Button
            type="primary"
            onClick={() => void save()}
            loading={busy}
            disabled={
              settings.enabled &&
              !models.some((model) => model.id === settings.model)
            }
          >
            {t("common.save")}
          </Button>
          <Button
            onClick={() => void probe()}
            loading={busy}
            disabled={!models.some((model) => model.id === settings.model)}
          >
            {t("models.decisionTest")}
          </Button>
        </Space>
        <p>{t("models.decisionFallback")}</p>
      </Space>
    </Card>
  );
}
