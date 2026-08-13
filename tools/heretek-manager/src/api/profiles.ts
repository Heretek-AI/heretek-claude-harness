import { Router } from "express";
import type { ProfileStore } from "../config/profiles.js";

export function createProfilesRouter(store: ProfileStore) {
  const router = Router();

  router.get("/", async (_req, res) => {
    const profiles = await store.list();
    const active = await store.getActive();
    res.json({ profiles, activeId: active?.id || null });
  });

  router.post("/", async (req, res) => {
    const profile = await store.create(req.body);
    res.status(201).json(profile);
  });

  router.put("/active", async (req, res) => {
    await store.setActive(req.body.id);
    res.json({ ok: true });
  });

  return router;
}
