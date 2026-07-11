import { Button, Result } from "antd";
import { useNavigate } from "react-router";

export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <main className="center-page">
      <Result
        status="404"
        title="404"
        subTitle="页面不存在，请检查地址。"
        extra={
          <Button type="primary" onClick={() => void navigate("/")}>
            返回首页
          </Button>
        }
      />
    </main>
  );
}
