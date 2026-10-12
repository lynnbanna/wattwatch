import { describe, expect, it } from "vitest";
import { apiUrl } from "./api";

describe("apiUrl", () => {
  it("prefixes paths with the versioned API base", () => {
    expect(apiUrl("health")).toBe("http://localhost:8000/api/v1/health");
  });

  it("tolerates a leading slash", () => {
    expect(apiUrl("/health")).toBe("http://localhost:8000/api/v1/health");
  });
});
