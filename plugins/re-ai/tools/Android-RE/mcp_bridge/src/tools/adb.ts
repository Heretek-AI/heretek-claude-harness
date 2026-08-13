/**
 * adb tools: list_devices, shell, pull, push, install, uninstall,
 * forward, reverse, getprop, setprop, list_packages, screencap,
 * screenrecord, dumpsys, input.
 */

import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { adbClient } from "../adb/client.js";
import { logger } from "../util/logger.js";

export function register(server: McpServer): void {
  // ----- adb_devices ---------------------------------------------------
  server.tool(
    "adb_devices",
    "List every device visible to adb.",
    {},
    async () => {
      try {
        const devs = await adbClient().listDevices();
        return { content: [{ type: "text", text: JSON.stringify({ count: devs.length, devices: devs }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_shell -----------------------------------------------------
  server.tool(
    "adb_shell",
    "Run an `adb shell <command>` on a device.",
    {
      serial: z.string().describe("Device serial"),
      command: z.string().describe("Shell command (e.g. 'ls /sdcard')"),
      timeout_ms: z.number().int().min(0).max(300_000).default(30_000).describe("Timeout in ms"),
    },
    async ({ serial, command, timeout_ms }) => {
      try {
        const { stdout, stderr, code } = await withTimeout(
          adbClient().shell(serial, command),
          timeout_ms
        );
        return {
          content: [
            { type: "text", text: JSON.stringify({ serial, command, exit_code: code, stdout, stderr_tail: stderr.slice(-1000) }) },
          ],
        };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_pull ------------------------------------------------------
  server.tool(
    "adb_pull",
    "Pull a file from the device to the host.",
    {
      serial: z.string().describe("Device serial"),
      src: z.string().describe("Source path on the device"),
      dst: z.string().describe("Destination path on the host"),
    },
    async ({ serial, src, dst }) => {
      try {
        await adbClient().pull(serial, src, dst);
        return { content: [{ type: "text", text: JSON.stringify({ ok: true, src, dst }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_push ------------------------------------------------------
  server.tool(
    "adb_push",
    "Push a file from the host to the device. Destructive: overwrites the target if it exists.",
    {
      serial: z.string().describe("Device serial"),
      src: z.string().describe("Source path on the host"),
      dst: z.string().describe("Destination path on the device"),
      confirm: z.boolean().describe("Must be true to push"),
    },
    async ({ serial, src, dst, confirm }) => {
      if (!confirm) {
        return { content: [{ type: "text", text: "error: adb_push requires confirm=true" }], isError: true };
      }
      try {
        await adbClient().push(serial, src, dst);
        return { content: [{ type: "text", text: JSON.stringify({ ok: true, src, dst }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_install ---------------------------------------------------
  server.tool(
    "adb_install",
    "Install an APK on a device. Requires confirm=true. Destructive: replaces existing package.",
    {
      serial: z.string().describe("Device serial"),
      apk_path: z.string().describe("Path to the .apk on the host"),
      replace: z.boolean().default(true).describe("Reinstall / replace existing"),
      confirm: z.boolean().describe("Must be true to install"),
    },
    async ({ serial, apk_path, replace, confirm }) => {
      if (!confirm) {
        return { content: [{ type: "text", text: "error: adb_install requires confirm=true" }], isError: true };
      }
      try {
        // adbkit's install() always replaces. To downgrade we'd need
        // to drop down to the adb shell — out of scope here.
        const out = await adbClient().install(serial, apk_path);
        return { content: [{ type: "text", text: JSON.stringify({ ok: true, apk_path, replace, output: out }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_uninstall -------------------------------------------------
  server.tool(
    "adb_uninstall",
    "Uninstall a package from a device. Requires confirm=true. Destructive.",
    {
      serial: z.string().describe("Device serial"),
      package: z.string().describe("Package identifier"),
      confirm: z.boolean().describe("Must be true to uninstall"),
    },
    async ({ serial, package: pkg, confirm }) => {
      if (!confirm) {
        return { content: [{ type: "text", text: "error: adb_uninstall requires confirm=true" }], isError: true };
      }
      try {
        const ok = await adbClient().uninstall(serial, pkg);
        return { content: [{ type: "text", text: JSON.stringify({ ok, package: pkg }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_forward ---------------------------------------------------
  server.tool(
    "adb_forward",
    "Forward a device-side TCP port to the host.",
    {
      serial: z.string().describe("Device serial"),
      device_port: z.number().int().min(1).max(65535).describe("Device-side port"),
      host_port: z.number().int().min(1).max(65535).describe("Host-side port"),
    },
    async ({ serial, device_port, host_port }) => {
      try {
        const out = await adbClient().forward(serial, host_port, device_port);
        return { content: [{ type: "text", text: JSON.stringify({ ok: true, serial, device_port, host_port, out }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_reverse ---------------------------------------------------
  server.tool(
    "adb_reverse",
    "Reverse-forward a host-side port to the device.",
    {
      serial: z.string().describe("Device serial"),
      device_port: z.number().int().min(1).max(65535).describe("Device-side port"),
      host_port: z.number().int().min(1).max(65535).describe("Host-side port"),
    },
    async ({ serial, device_port, host_port }) => {
      try {
        const out = await adbClient().reverse(serial, device_port, host_port);
        return { content: [{ type: "text", text: JSON.stringify({ ok: true, serial, device_port, host_port, out }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_logcat ----------------------------------------------------
  server.tool(
    "adb_logcat",
    "Fetch logcat from a device. Set follow=true to stream.",
    {
      serial: z.string().describe("Device serial"),
      package: z.string().optional().describe("Filter lines containing this package name"),
      level: z.enum(["V", "D", "I", "W", "E", "F"]).default("I").describe("Minimum level"),
      max_lines: z.number().int().min(1).max(2000).default(200).describe("Max lines to return"),
      follow: z.boolean().default(false).describe("If true, return a follow token (streaming not yet supported)"),
    },
    async ({ serial, package: pkg, level, max_lines, follow }) => {
      try {
        // adbkit doesn't expose a streaming logcat; we use shell to
        // run `logcat -d` (one-shot) or `logcat -T 0` (continuous).
        const filterArg = `${level}:*`;
        const pkgArg = pkg ? ` | grep ${shellQuote(pkg)}` : "";
        const cmd = follow
          ? `logcat -T 0 -v time ${filterArg}${pkgArg}`
          : `logcat -d -v time ${filterArg}${pkgArg}`;
        const { stdout, code } = await withTimeout(
          adbClient().shell(serial, cmd),
          follow ? 60_000 : 15_000
        );
        const lines = stdout.split("\n").slice(-max_lines);
        if (follow) {
          return {
            content: [
              {
                type: "text",
                text: JSON.stringify({
                  note: "Streaming not yet supported in TS bridge; one-shot returned.",
                  lines,
                  line_count: lines.length,
                }),
              },
            ],
          };
        }
        return { content: [{ type: "text", text: JSON.stringify({ exit_code: code, lines, line_count: lines.length }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_screencap -------------------------------------------------
  server.tool(
    "adb_screencap",
    "Capture a PNG screenshot of the current device screen.",
    {
      serial: z.string().describe("Device serial"),
      output_path: z.string().describe("Host path to write the PNG to"),
    },
    async ({ serial, output_path }) => {
      try {
        await adbClient().screencap(serial, output_path);
        return { content: [{ type: "text", text: JSON.stringify({ ok: true, output_path }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_screenrecord ----------------------------------------------
  server.tool(
    "adb_screenrecord",
    "Record the screen to an MP4. Returns after the duration elapses.",
    {
      serial: z.string().describe("Device serial"),
      duration_s: z.number().int().min(1).max(180).default(10).describe("Recording length"),
      output_path: z.string().describe("Host path to write the MP4 to"),
    },
    async ({ serial, duration_s, output_path }) => {
      try {
        // adbkit has no screenrecord helper; use shell
        const remote = "/sdcard/screenrecord.mp4";
        await withTimeout(
          adbClient().shell(serial, `screenrecord --time-limit ${duration_s} ${remote}`),
          (duration_s + 30) * 1000
        );
        await adbClient().pull(serial, remote, output_path);
        await adbClient().shell(serial, `rm ${remote}`);
        return { content: [{ type: "text", text: JSON.stringify({ ok: true, output_path, duration_s }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_getprop ---------------------------------------------------
  server.tool(
    "adb_getprop",
    "Read a system property via `adb shell getprop`.",
    {
      serial: z.string().describe("Device serial"),
      prop: z.string().optional().describe("Specific property to read; if omitted, returns all"),
    },
    async ({ serial, prop }) => {
      try {
        if (prop) {
          const value = await adbClient().getprop(serial, prop);
          return { content: [{ type: "text", text: JSON.stringify({ prop, value }) }] };
        }
        const { stdout } = await withTimeout(adbClient().shell(serial, "getprop"), 10_000);
        const lines = stdout
          .split("\n")
          .map((l) => l.trim())
          .filter((l) => l.length > 0 && l.includes(": "))
          .map((l) => {
            const idx = l.indexOf(": ");
            return { prop: l.slice(0, idx), value: l.slice(idx + 2) };
          });
        return { content: [{ type: "text", text: JSON.stringify({ count: lines.length, properties: lines }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_setprop ---------------------------------------------------
  server.tool(
    "adb_setprop",
    "Set a system property. Requires root on userdebug builds.",
    {
      serial: z.string().describe("Device serial"),
      prop: z.string().describe("Property name"),
      value: z.string().describe("New value"),
    },
    async ({ serial, prop, value }) => {
      try {
        await adbClient().setprop(serial, prop, value);
        return { content: [{ type: "text", text: JSON.stringify({ ok: true, prop, value }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_list_packages --------------------------------------------
  server.tool(
    "adb_list_packages",
    "List installed packages.",
    {
      serial: z.string().describe("Device serial"),
      filter: z.enum(["all", "system", "thirdparty"]).default("all").describe("Package filter"),
    },
    async ({ serial, filter }) => {
      try {
        const packages = await adbClient().listPackages(serial, filter === "all" ? undefined : filter);
        return { content: [{ type: "text", text: JSON.stringify({ count: packages.length, packages }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_dumpsys ---------------------------------------------------
  server.tool(
    "adb_dumpsys",
    "Run `adb shell dumpsys <service>` and return the output.",
    {
      serial: z.string().describe("Device serial"),
      service: z.string().describe("Service name, e.g. 'activity' or 'package'"),
      args: z.array(z.string()).optional().describe("Additional args to pass"),
    },
    async ({ serial, service, args }) => {
      try {
        const out = await adbClient().dumpsys(serial, service, args);
        return { content: [{ type: "text", text: JSON.stringify({ service, length: out.length, output_tail: out.slice(-2000) }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  // ----- adb_input ----------------------------------------------------
  server.tool(
    "adb_input",
    "Send an input event: tap, swipe, or keyevent.",
    {
      serial: z.string().describe("Device serial"),
      action: z.enum(["tap", "swipe", "keyevent", "text"]).describe("Input action"),
      x: z.number().int().optional().describe("X coordinate (for tap / swipe)"),
      y: z.number().int().optional().describe("Y coordinate (for tap / swipe)"),
      x2: z.number().int().optional().describe("X end coordinate (swipe only)"),
      y2: z.number().int().optional().describe("Y end coordinate (swipe only)"),
      duration_ms: z.number().int().min(0).max(60_000).default(300).describe("Swipe duration in ms"),
      keycode: z.number().int().optional().describe("Android keycode (for keyevent)"),
      text: z.string().optional().describe("Text to type (for text)"),
    },
    async ({ serial, action, x, y, x2, y2, duration_ms, keycode, text }) => {
      try {
        let cmd: string;
        switch (action) {
          case "tap":
            if (x === undefined || y === undefined) {
              return { content: [{ type: "text", text: "error: tap requires x and y" }], isError: true };
            }
            cmd = `input tap ${x} ${y}`;
            break;
          case "swipe":
            if (x === undefined || y === undefined || x2 === undefined || y2 === undefined) {
              return { content: [{ type: "text", text: "error: swipe requires x, y, x2, y2" }], isError: true };
            }
            cmd = `input swipe ${x} ${y} ${x2} ${y2} ${duration_ms}`;
            break;
          case "keyevent":
            if (keycode === undefined) {
              return { content: [{ type: "text", text: "error: keyevent requires keycode" }], isError: true };
            }
            cmd = `input keyevent ${keycode}`;
            break;
          case "text":
            if (!text) {
              return { content: [{ type: "text", text: "error: text requires text" }], isError: true };
            }
            cmd = `input text ${shellQuote(text)}`;
            break;
        }
        const { stdout, code } = await withTimeout(adbClient().shell(serial, cmd), 10_000);
        return { content: [{ type: "text", text: JSON.stringify({ ok: code === 0, action, stdout }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  if (ms <= 0) {
    return promise;
  }
  return new Promise<T>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`timeout after ${ms}ms`)), ms);
    promise.then(
      (v) => {
        clearTimeout(t);
        resolve(v);
      },
      (e) => {
        clearTimeout(t);
        reject(e);
      }
    );
  });
}

function shellQuote(s: string): string {
  return `'${s.replace(/'/g, "'\\''")}'`;
}

void logger;
