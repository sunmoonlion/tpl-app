import { ApiError, apiRequest } from "~/lib/api";

describe("apiRequest", () => {
  it("uses credentials and parses a successful response", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await expect(apiRequest<{ ok: boolean }>("/api/example")).resolves.toEqual({
      ok: true,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/example"),
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("normalizes non-json failures without trusting response text", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("<script>unsafe</script>", {
        status: 503,
        headers: { "x-correlation-id": "corr-1" },
      }),
    );

    const error = await apiRequest("/api/example").catch(
      (reason: unknown) => reason,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 503,
      detail: { code: "http_error", retryable: true, correlation_id: "corr-1" },
    });
  });
});
