/**
 * adbkit client wrapper.
 *
 * adbkit exposes an async connection-pooled ADB client. We add a
 * single adbClient() factory and a one-shot exec() helper for the
 * common case of running an arbitrary command on a single device.
 */

import adb from "adbkit";

export interface AdbClient {
  listDevices(): Promise<{ id: string; type: string }[]>;
  shell(serial: string, command: string): Promise<{ stdout: string; stderr: string; code: number }>;
  pull(serial: string, src: string, dst: string): Promise<void>;
  push(serial: string, src: string, dst: string): Promise<void>;
  install(serial: string, apk: string): Promise<string>;
  uninstall(serial: string, pkg: string): Promise<boolean>;
  forward(serial: string, hostPort: number, devicePort: number): Promise<string>;
  reverse(serial: string, devicePort: number, hostPort: number): Promise<string>;
  getprop(serial: string, prop: string): Promise<string>;
  setprop(serial: string, prop: string, value: string): Promise<void>;
  listPackages(serial: string, filter?: string): Promise<string[]>;
  screencap(serial: string, outPath: string): Promise<void>;
  dumpsys(serial: string, service: string, args?: string[]): Promise<string>;
}

let _client: AdbClient | null = null;

export function adbClient(): AdbClient {
  if (_client !== null) {
    return _client;
  }
  const c = adb.createClient();
  _client = wrap(c);
  return _client;
}

function wrap(c: ReturnType<typeof adb.createClient>): AdbClient {
  return {
    async listDevices() {
      const devices = await c.listDevices();
      return devices.map((d: { id: string; type: string }) => ({ id: d.id, type: d.type }));
    },
    async shell(serial: string, command: string) {
      const transport = await c.shell(serial, command);
      let stdout = "";
      let stderr = "";
      transport.on("stdout", (data: Buffer) => {
        stdout += data.toString("utf-8");
      });
      transport.on("stderr", (data: Buffer) => {
        stderr += data.toString("utf-8");
      });
      return new Promise<{ stdout: string; stderr: string; code: number }>((resolve, reject) => {
        transport.on("error", reject);
        transport.on("exit", (code: number) => {
          resolve({ stdout, stderr, code });
        });
      });
    },
    async pull(serial: string, src: string, dst: string) {
      const transfer = await c.pull(serial, src);
      await new Promise<void>((resolve, reject) => {
        transfer.on("error", reject);
        transfer.on("end", () => resolve());
        transfer.pipe(require("fs").createWriteStream(dst));
      });
    },
    async push(serial: string, src: string, dst: string) {
      const transfer = await c.push(serial, src, dst);
      await new Promise<void>((resolve, reject) => {
        transfer.on("error", reject);
        transfer.on("end", () => resolve());
      });
    },
    async install(serial: string, apk: string) {
      return await c.install(serial, apk);
    },
    async uninstall(serial: string, pkg: string) {
      return await c.uninstall(serial, pkg);
    },
    async forward(serial: string, hostPort: number, devicePort: number) {
      return await c.forward(serial, `tcp:${hostPort}`, `tcp:${devicePort}`);
    },
    async reverse(serial: string, devicePort: number, hostPort: number) {
      return await c.reverse(serial, `tcp:${devicePort}`, `tcp:${hostPort}`);
    },
    async getprop(serial: string, prop: string) {
      const { stdout } = await this.shell(serial, `getprop "${prop}"`);
      return stdout.trim();
    },
    async setprop(serial: string, prop: string, value: string) {
      await this.shell(serial, `setprop "${prop}" "${value}"`);
    },
    async listPackages(serial: string, filter?: string) {
      const pmArg = filter === "system" ? "-s" : filter === "thirdparty" ? "-3" : "";
      const { stdout } = await this.shell(serial, `pm list packages ${pmArg}`.trim());
      return stdout
        .split("\n")
        .map((line) => line.replace(/^package:/, "").trim())
        .filter((line) => line.length > 0);
    },
    async screencap(serial: string, outPath: string) {
      const transfer = await c.screencap(serial);
      await new Promise<void>((resolve, reject) => {
        transfer.on("error", reject);
        transfer.on("end", () => resolve());
        transfer.pipe(require("fs").createWriteStream(outPath));
      });
    },
    async dumpsys(serial: string, service: string, args: string[] = []) {
      const cmd = ["dumpsys", service, ...args].join(" ");
      const { stdout } = await this.shell(serial, cmd);
      return stdout;
    },
  };
}
