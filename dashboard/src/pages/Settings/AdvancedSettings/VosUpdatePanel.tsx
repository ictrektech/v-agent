import { useState } from "react";
import { updateApi } from "../../../api/modules/update";
import { storeUpdateStatus } from "../../../utils/updateStatusCache";
import { Button, Descriptions, Alert, Space } from "antd";
import { useTranslation } from "react-i18next";
import { useUpdateStatus } from "../../../hooks/useUpdateStatus";
export default function VosUpdatePanel() {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const { status } = useUpdateStatus();
  const [checking, setChecking] = useState(false);
  const check = async () => {
    setChecking(true);
    try {
      storeUpdateStatus(await updateApi.checkForUpdates());
    } finally {
      setChecking(false);
    }
  };
  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Alert
        type="info"
        showIcon
        message={
          zh
            ? "v-agent 通过 VOS 应用商店升级，保留各用户的数据和工作区。"
            : "Upgrade v-agent through the VOS App Store. User data and workspaces are retained."
        }
      />
      <Descriptions
        bordered
        column={1}
        items={[
          {
            key: "current",
            label: zh ? "当前 VOS 应用版本" : "Installed VOS app version",
            children: status?.current_version ?? "—",
          },
          {
            key: "latest",
            label: zh ? "最新发布版本" : "Latest release",
            children: status?.latest_version ?? "—",
          },
          {
            key: "source",
            label: zh ? "更新源" : "Release source",
            children: (
              <a
                href="https://github.com/ictrektech/v-agent/releases"
                target="_blank"
                rel="noreferrer"
              >
                ictrektech/v-agent Releases
              </a>
            ),
          },
        ]}
      />
      {status?.error && (
        <Alert
          type="warning"
          message={
            zh
              ? "暂时无法读取 fork 的发布版本，请稍后重试。"
              : "Could not check this fork's releases. Try again later."
          }
        />
      )}
      <Button loading={checking} onClick={() => void check()}>
        {zh ? "检查更新" : "Check for updates"}
      </Button>
    </Space>
  );
}
