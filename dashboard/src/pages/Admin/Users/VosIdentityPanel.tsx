import { useEffect, useState } from "react";
import { Alert, Descriptions, Spin } from "antd";
import { useTranslation } from "react-i18next";
import PageShell from "../../../layouts/PageShell";

export default function VosIdentityPanel() {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const [identity, setIdentity] = useState<{
    subject: string;
    username: string;
    login_method: string;
  }>();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}__va/identity`, {
      credentials: "same-origin",
    })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then(setIdentity)
      .catch(() => setFailed(true));
  }, []);
  return (
    <PageShell
      title={zh ? "VOS 用户" : "VOS account"}
      subtitle={
        zh
          ? "账号、角色和登录方式由 VOS 统一管理"
          : "Accounts, roles and sign-in are managed by VOS"
      }
    >
      <Alert
        type="info"
        showIcon
        message={
          zh
            ? "每个 VOS 用户对应一个独立的 v-octop 账号和工作区。请在 VOS 系统设置中管理用户。"
            : "Each VOS user has a separate v-octop account and workspace. Manage users in VOS system settings."
        }
      />
      {failed ? (
        <Alert
          type="error"
          message={
            zh
              ? "无法读取 VOS 身份，请刷新后重试。"
              : "Could not load the VOS identity. Refresh to retry."
          }
        />
      ) : !identity ? (
        <Spin />
      ) : (
        <Descriptions
          bordered
          column={1}
          style={{ marginTop: 24 }}
          items={[
            {
              key: "username",
              label: zh ? "用户名" : "Username",
              children: identity.username,
            },
            {
              key: "subject",
              label: zh ? "VOS 用户 ID" : "VOS user ID",
              children: identity.subject,
            },
            {
              key: "login",
              label: zh ? "登录方式" : "Sign-in",
              children: identity.login_method,
            },
          ]}
        />
      )}
    </PageShell>
  );
}
