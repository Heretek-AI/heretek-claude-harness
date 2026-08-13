import { readFile, writeFile, readdir, mkdir } from "fs/promises";
import { join } from "path";
import { randomUUID } from "crypto";

export interface Profile {
  id: string;
  name: string;
  providers: Record<string, Record<string, unknown>>;
  defaults: {
    model: string;
    temperature: number;
    maxTokens: number;
  };
}

export class ProfileStore {
  private dir: string;

  constructor(dir: string) {
    this.dir = dir;
  }

  async list(): Promise<Profile[]> {
    await mkdir(this.dir, { recursive: true });
    const files = await readdir(this.dir);
    const profiles: Profile[] = [];
    for (const file of files) {
      if (!file.endsWith(".json")) continue;
      const content = await readFile(join(this.dir, file), "utf-8");
      profiles.push(JSON.parse(content));
    }
    return profiles;
  }

  async create(
    data: Omit<Profile, "id">
  ): Promise<Profile> {
    const profile: Profile = { ...data, id: randomUUID() };
    await mkdir(this.dir, { recursive: true });
    await writeFile(
      join(this.dir, `${profile.id}.json`),
      JSON.stringify(profile, null, 2)
    );
    return profile;
  }

  async getActive(): Promise<Profile | null> {
    const activeFile = join(this.dir, ".active");
    try {
      const id = (await readFile(activeFile, "utf-8")).trim();
      const content = await readFile(join(this.dir, `${id}.json`), "utf-8");
      return JSON.parse(content);
    } catch {
      return null;
    }
  }

  async setActive(id: string): Promise<void> {
    await writeFile(join(this.dir, ".active"), id);
  }
}
