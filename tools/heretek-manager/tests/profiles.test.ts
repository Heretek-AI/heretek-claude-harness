import { describe, it, expect, beforeEach } from "vitest";
import { ProfileStore } from "../src/config/profiles.js";
import { mkdirSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

let store: ProfileStore;
let testDir: string;

beforeEach(() => {
  testDir = join(tmpdir(), `test-profiles-${Date.now()}`);
  mkdirSync(testDir, { recursive: true });
  store = new ProfileStore(testDir);
});

describe("ProfileStore", () => {
  it("lists empty profiles", async () => {
    const profiles = await store.list();
    expect(profiles).toEqual([]);
  });

  it("creates and retrieves a profile", async () => {
    const profile = await store.create({
      name: "default",
      providers: {},
      defaults: { model: "gpt-4", temperature: 0.7, maxTokens: 4096 },
    });
    expect(profile.id).toBeTruthy();
    expect(profile.name).toBe("default");

    const profiles = await store.list();
    expect(profiles).toHaveLength(1);
    expect(profiles[0].name).toBe("default");
  });

  it("switches active profile", async () => {
    await store.create({
      name: "profile-a",
      providers: {},
      defaults: { model: "gpt-4", temperature: 0.7, maxTokens: 4096 },
    });
    const b = await store.create({
      name: "profile-b",
      providers: {},
      defaults: { model: "claude-3", temperature: 0.5, maxTokens: 8192 },
    });

    await store.setActive(b.id);
    const active = await store.getActive();
    expect(active?.name).toBe("profile-b");
  });
});
