import { Button, Result, Space, Typography } from "antd";
import { isRouteErrorResponse, useNavigate, useRouteError } from "react-router";

export function RouteErrorBoundary() {
  const error = useRouteError();
  const navigate = useNavigate();
  const status = isRouteErrorResponse(error) ? error.status : 500;
  const detail = isRouteErrorResponse(error)
    ? typeof error.data === "string"
      ? error.data
      : error.statusText
    : error instanceof Error
      ? error.message
      : "页面加载失败，请稍后重试。";

  return (
    <main className="center-page" role="alert">
      <Result
        status={status === 404 ? 404 : "error"}
        title={status === 404 ? "页面不存在" : "页面暂时不可用"}
        subTitle={
          <Typography.Text type="secondary">{detail}</Typography.Text>
        }
        extra={
          <Space>
            <Button onClick={() => navigate(-1)}>返回上一页</Button>
            <Button type="primary" onClick={() => void navigate("/")}>
              返回首页
            </Button>
          </Space>
        }
      />
    </main>
  );
}
