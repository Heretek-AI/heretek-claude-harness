/**
 * Minimal type declaration for adbkit.
 *
 * adbkit has no published .d.ts file. This stub declares the surface
 * we actually use. If we need more APIs later, add them here.
 */

declare module "adbkit" {
  export interface AdbDevice {
    id: string;
    type: string;
  }
  export interface AdbClient {
    listDevices(): Promise<AdbDevice[]>;
    shell(serial: string, command: string): Promise<NodeJS.ReadableStream & { on(ev: string, cb: (...args: unknown[]) => void): unknown }>;
    pull(serial: string, path: string): Promise<NodeJS.ReadableStream & { on(ev: string, cb: (...args: unknown[]) => void): unknown }>;
    push(serial: string, src: string, dst: string): Promise<NodeJS.WritableStream & { on(ev: string, cb: (...args: unknown[]) => void): unknown }>;
    install(serial: string, apk: string): Promise<string>;
    uninstall(serial: string, pkg: string): Promise<boolean>;
    forward(serial: string, local: string, remote: string): Promise<string>;
    reverse(serial: string, local: string, remote: string): Promise<string>;
    screencap(serial: string): Promise<NodeJS.ReadableStream & { on(ev: string, cb: (...args: unknown[]) => void): unknown }>;
  }
  export function createClient(opts?: Record<string, unknown>): AdbClient;
  const _default: { createClient: typeof createClient };
  export default _default;
}
