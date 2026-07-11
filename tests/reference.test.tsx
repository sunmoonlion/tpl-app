import { fireEvent, render, screen } from "@testing-library/react";

import ReferencePage from "~/routes/reference";

describe("ReferencePage", () => {
  it("filters rows and exposes an empty state", () => {
    render(<ReferencePage />);
    expect(screen.getByText("Contract client")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("筛选名称"), {
      target: { value: "missing" },
    });
    expect(screen.getByText("没有符合条件的数据")).toBeInTheDocument();
  });

  it("requires a reason for the audited operation", () => {
    render(<ReferencePage />);
    fireEvent.click(screen.getByRole("button", { name: "新建操作" }));
    const reason = screen.getByPlaceholderText("请输入至少 5 个字符");
    expect(reason).toBeRequired();
    expect(reason).toHaveAttribute("minLength", "5");
  });
});
