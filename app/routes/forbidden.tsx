import { Button, Result } from "antd";
import { useNavigate } from "react-router";

export default function ForbiddenPage() {
  const navigate = useNavigate();
  return (
    <Result
      status="403"
      title="403"
      subTitle="当前身份不能访问这个页面。"
      extra={
        <Button type="primary" onClick={() => void navigate("/")}>
          返回首页
        </Button>
      }
    />
  );
}
