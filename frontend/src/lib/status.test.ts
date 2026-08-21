import { describe, expect, it } from "vitest";
import { isDevelopment, statusLabel, statusTone } from "./status";

describe("status model", () => {
  it("labels development without implying runtime", () => {
    expect(statusLabel("IN_DEVELOPMENT")).toBe("In development");
    expect(statusLabel("not_implemented")).toBe("In development");
    expect(isDevelopment("in_development", "IN_DEVELOPMENT")).toBe(true);
  });

  it("does not treat unknown as healthy", () => {
    expect(statusTone("UNKNOWN")).toBe("neutral");
    expect(statusTone("healthy")).toBe("healthy");
    expect(statusLabel("UNKNOWN")).toBe("Unknown");
  });
});
