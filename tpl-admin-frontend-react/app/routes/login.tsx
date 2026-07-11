import { Button, Card, Space, Typography } from "antd";
import { LogIn } from "lucide-react";
import { Link, useSearchParams } from "react-router";

import { loginUrl } from "~/lib/auth";
import { appConfig } from "~/lib/config";

export function meta() {
  return [{ title: `登录 · ${appConfig.name}` }];
}

export default function LoginPage() {
  const [params] = useSearchParams();
  const returnTo = params.get("return_to") || "/";
  return (
    <main className="login-page">
      <Card className="login-card">
        <Space direction="vertical" size="middle" className="full-width">
          <div className="brand-mark large">S</div>
          <div>
            <Typography.Text type="secondary">{appConfig.name}</Typography.Text>
            <Typography.Title level={1}>欢迎回来</Typography.Title>
            <Typography.Paragraph type="secondary">
              使用 Casdoor 单点登录进入管理后台
            </Typography.Paragraph>
          </div>
          <Button
            type="primary"
            size="large"
            block
            icon={<LogIn size={18} />}
            href={loginUrl(returnTo)}
          >
            使用 Casdoor 登录
          </Button>
          <Link className="subtle-link" to="/">
            返回首页
          </Link>
        </Space>
      </Card>
    </main>
  );
}
