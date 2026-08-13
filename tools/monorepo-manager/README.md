# monorepo-manager

Throwaway workspace for the Heretek AI harness. Generates the harness
that gets installed into `Heretek-AI/llama-builds` and
`Heretek-AI/heretek-manager`.

**Spec:** [`docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md`](docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md)

**Plan:** [`docs/superpowers/plans/2026-08-01-monorepo-manager-harness-impl.md`](docs/superpowers/plans/2026-08-01-monorepo-manager-harness-impl.md)

**Generate a child install:**

```bash
scripts/init-harness.sh --target reference/llama-builds-install --name llama-builds --stack python
```

**Validate:**

```bash
pytest tests/
```

## Tracking

- Spec tracking Issue: *to be filed after spec approval*
- Roadmap project: *to be created during child v1*
- Sonar project: N/A (umbrella has no app code)
