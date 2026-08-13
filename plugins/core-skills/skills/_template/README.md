# Template skill

This directory is **not** an installed skill. It is a starter scaffold for contributors who want to add a new skill to this repository.

The `_` prefix on the directory name is intentional — it tells skills registries (e.g., `npx skills`, `skills-ref`) to skip this folder. Only skills without an underscore prefix are published as installable.

## How to use this template

1. **Copy the directory** to a new name:

   ```bash
   cp -r skills/_template skills/<your-skill-name>
   ```

2. **Edit `SKILL.md`**:
   - Replace `<skill-name>` in the YAML frontmatter with the directory name (they must match exactly).
   - Replace `<Skill Title>` and the body content.
   - Fill in the `description` field with trigger phrases — this is what makes the skill discoverable.

3. **Add supporting files** if needed:
   - `references/<topic>.md` — distilled docs.
   - `scripts/<name>.sh` — helper scripts.
   - `assets/<template>.kt` — starter files.

4. **Validate locally**:

   ```bash
   npx -y skills-ref validate skills/<your-skill-name>
   ```

5. **Open a PR.** CI will run validation and check that the README's skill list reflects the new skill.

## Conventions

- `name` (frontmatter) must **exactly match** the parent directory.
- `description` must be ≤ 1024 chars and include "when to use" trigger phrases.
- Keep `SKILL.md` body under 500 lines. Move deep content into `references/`.
- Use MIT-licensed code only. Distill any third-party documentation you reference — do not copy verbatim.
