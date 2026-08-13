import { Router } from "express";
import type { AIProvider } from "../providers/types.js";

export function createModelsRouter(registry: Map<string, AIProvider>) {
  const router = Router();

  router.get("/", async (_req, res) => {
    const allModels = [];
    for (const provider of registry.values()) {
      try {
        const models = await provider.listModels();
        allModels.push(...models);
      } catch {
        // skip failed providers
      }
    }
    res.json({ models: allModels });
  });

  return router;
}
