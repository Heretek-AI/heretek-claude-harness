import { Router } from "express";
import type { AIProvider } from "../providers/types.js";

export function createProvidersRouter(registry: Map<string, AIProvider>) {
  const router = Router();

  router.get("/", (_req, res) => {
    const providers = Array.from(registry.values()).map((p) => ({
      id: p.id,
      name: p.name,
      type: p.type,
    }));
    res.json({ providers });
  });

  router.get("/:id/health", async (req, res) => {
    const provider = registry.get(req.params.id);
    if (!provider) {
      res.status(404).json({ error: "Provider not found" });
      return;
    }
    const health = await provider.health();
    res.json(health);
  });

  return router;
}
