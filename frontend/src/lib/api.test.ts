import { describe, expect, it } from "vitest";
import { apiErrorMessage, apiUrl, MAX_UPLOAD_BYTES, validateImageFile } from "./api";

describe("apiUrl", () => {
  it("prefixes paths with the versioned API base", () => {
    expect(apiUrl("health")).toBe("http://localhost:8000/api/v1/health");
  });

  it("tolerates a leading slash", () => {
    expect(apiUrl("/health")).toBe("http://localhost:8000/api/v1/health");
  });
});

describe("validateImageFile", () => {
  it("accepts PNG and JPEG within the size limit", () => {
    expect(validateImageFile({ type: "image/png", size: 1024 })).toBeNull();
    expect(validateImageFile({ type: "image/jpeg", size: MAX_UPLOAD_BYTES })).toBeNull();
  });

  it("rejects other types", () => {
    expect(validateImageFile({ type: "image/gif", size: 1024 })).toMatch(/PNG or JPEG/);
  });

  it("rejects files over the upload limit", () => {
    expect(validateImageFile({ type: "image/png", size: MAX_UPLOAD_BYTES + 1 })).toMatch(
      /10 MB/,
    );
  });
});

describe("apiErrorMessage", () => {
  it("uses the message from the standard error shape", () => {
    const body = { error: { code: "file_too_large", message: "File exceeds the limit" } };
    expect(apiErrorMessage(413, body)).toBe("File exceeds the limit");
  });

  it("falls back to the status when the body is not the standard shape", () => {
    expect(apiErrorMessage(502, null)).toBe("Request failed with status 502");
    expect(apiErrorMessage(500, { detail: "x" })).toBe("Request failed with status 500");
  });
});
