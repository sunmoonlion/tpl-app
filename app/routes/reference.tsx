import {
  Button,
  Card,
  Descriptions,
  Drawer,
  Form,
  Input,
  Modal,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import { useMemo, useState } from "react";

import { appConfig } from "~/lib/config";

interface ReferenceRow {
  id: string;
  name: string;
  status: "ready" | "pending" | "failed";
  owner: string;
  updatedAt: string;
}

const rows: ReferenceRow[] = [
  {
    id: "ref-001",
    name: "Contract client",
    status: "ready",
    owner: "Platform",
    updatedAt: "2026-07-11",
  },
  {
    id: "ref-002",
    name: "Async operation",
    status: "pending",
    owner: "Worker",
    updatedAt: "2026-07-10",
  },
  {
    id: "ref-003",
    name: "Failure handling",
    status: "failed",
    owner: "Operator",
    updatedAt: "2026-07-09",
  },
];

const statusColor = { ready: "green", pending: "gold", failed: "red" } as const;

export function meta() {
  return [{ title: `参考页面 · ${appConfig.name}` }];
}

export default function ReferencePage() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<ReferenceRow | null>(null);
  const [reasonOpen, setReasonOpen] = useState(false);
  const [form] = Form.useForm<{ reason: string }>();
  const filtered = useMemo(
    () =>
      rows.filter((row) =>
        row.name.toLowerCase().includes(query.toLowerCase()),
      ),
    [query],
  );
  const columns: TableColumnsType<ReferenceRow> = [
    {
      title: "ID",
      dataIndex: "id",
      render: (value: string) => (
        <Typography.Text code>{value}</Typography.Text>
      ),
    },
    { title: "名称", dataIndex: "name" },
    {
      title: "状态",
      dataIndex: "status",
      render: (value: ReferenceRow["status"]) => (
        <Tag color={statusColor[value]}>{value}</Tag>
      ),
    },
    { title: "负责人", dataIndex: "owner" },
    { title: "更新时间", dataIndex: "updatedAt" },
    {
      title: "操作",
      key: "actions",
      render: (_, row) => (
        <Button type="link" onClick={() => setSelected(row)}>
          详情
        </Button>
      ),
    },
  ];

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <Typography.Text type="secondary">Reference pattern</Typography.Text>
          <Typography.Title level={1}>表格与操作参考页</Typography.Title>
          <Typography.Paragraph type="secondary">
            对应 Vue/Element Plus 中常见的筛选、Table、Tag、Drawer、Modal 和
            Form。
          </Typography.Paragraph>
        </div>
        <Button type="primary" onClick={() => setReasonOpen(true)}>
          新建操作
        </Button>
      </header>

      <Card>
        <Space wrap className="reference-toolbar">
          <Input.Search
            allowClear
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="筛选名称"
          />
          <Button onClick={() => setQuery("")}>重置</Button>
        </Space>
        <Table<ReferenceRow>
          rowKey="id"
          columns={columns}
          dataSource={filtered}
          scroll={{ x: 760 }}
          locale={{ emptyText: "没有符合条件的数据" }}
          pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条` }}
        />
      </Card>

      <Drawer
        title="操作详情"
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        size="large"
      >
        {selected && (
          <Descriptions
            column={1}
            bordered
            size="small"
            items={[
              { key: "id", label: "ID", children: selected.id },
              { key: "name", label: "名称", children: selected.name },
              {
                key: "status",
                label: "状态",
                children: (
                  <Tag color={statusColor[selected.status]}>
                    {selected.status}
                  </Tag>
                ),
              },
              { key: "owner", label: "负责人", children: selected.owner },
            ]}
          />
        )}
      </Drawer>

      <Modal
        title="确认受审计操作"
        open={reasonOpen}
        okText="确认"
        cancelText="取消"
        onCancel={() => {
          setReasonOpen(false);
          form.resetFields();
        }}
        onOk={() =>
          void form.validateFields().then(() => {
            setReasonOpen(false);
            form.resetFields();
          })
        }
      >
        <Form form={form} layout="vertical" requiredMark>
          <Form.Item
            name="reason"
            label="操作原因"
            rules={[{ required: true, min: 5, message: "请输入至少 5 个字符" }]}
          >
            <Input.TextArea
              required
              minLength={5}
              rows={4}
              placeholder="请输入至少 5 个字符"
            />
          </Form.Item>
        </Form>
      </Modal>
    </section>
  );
}
