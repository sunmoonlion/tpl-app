import { Alert, Card, Col, Row, Statistic, Typography } from "antd";
import { Activity, Boxes, ShieldCheck } from "lucide-react";

import { appConfig } from "~/lib/config";

export function meta() {
  return [{ title: `首页 · ${appConfig.name}` }];
}

const metrics = [
  { title: "运行状态", value: "Ready", icon: <Activity /> },
  { title: "模板模式", value: "SPA", icon: <Boxes /> },
  { title: "认证模式", value: "Session", icon: <ShieldCheck /> },
];

export default function HomePage() {
  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <Typography.Text type="secondary">Dashboard</Typography.Text>
          <Typography.Title level={1}>管理首页</Typography.Title>
          <Typography.Paragraph type="secondary">
            React 模板保持 Vue Admin 熟悉的导航与内容层级，内部采用标准 React
            数据流。
          </Typography.Paragraph>
        </div>
      </header>
      <Row gutter={[16, 16]}>
        {metrics.map((metric) => (
          <Col xs={24} md={8} key={metric.title}>
            <Card>
              <div className="metric-content">
                <span className="metric-icon">{metric.icon}</span>
                <Statistic title={metric.title} value={metric.value} />
              </div>
            </Card>
          </Col>
        ))}
      </Row>
      <Alert
        showIcon
        type="info"
        message="职责边界"
        description="Router 管理页面进入、pending 与 error；TanStack Query 管理服务端状态；Zustand 只保存侧栏和标签等 UI 偏好。"
      />
    </section>
  );
}
