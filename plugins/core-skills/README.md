# Heretek Skills

Agent skills for creating [Morphe](https://morphe.software) patches. Each skill is a self-contained module that teaches an AI agent (Claude Code, Cursor, etc.) how to perform a specific Morphe task.

## Install

```bash
npx skills add Heretek-AI/heretek-skills
```

Or install a single skill:

```bash
npx skills add Heretek-AI/heretek-skills --skill create-morphe-patch
```

## Available skills

| Skill | Description |
|---|---|
| [`create-morphe-patch`](./skills/create-morphe-patch/) | Author a new Morphe patch: signature capture, fingerprinting, the `Compatibility` block, optional `.mpe` extensions, and Gradle build verification. |

## Future skills

These are planned but not yet implemented. Each will be extracted only when its content exceeds a self-contained section in the current skill.

- `fingerprint-morphe-method` — when fingerprint authoring alone grows past a self-contained section.
- `package-morphe-bundle` — when "how do I publish a `.mpp`" becomes a recurring question.
- `extend-morphe-patch-with-mpe` — when `.mpe` extension authoring needs its own workflow.
- `compat-block-for-app` — when `Compatibility` becomes its own generator/validator.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for how to add a new skill.

## License

The skill code, templates, and scripts in this repository are released under the **MIT License** — see [LICENSE](./LICENSE).

**Note on generated artifacts:** Skills here teach how to build Morphe patches. The `.mpp` and `.mpe` artifacts you produce are *derived works of Morphe patcher* and inherit the upstream **GPLv3 with Section 7 Additional Terms**. Read [Morphe Patcher LICENSE](https://github.com/MorpheApp/morphe-patcher/blob/main/LICENSE) before publishing derivative bundles. Section 7 places restrictions on reuse of the Morphe name and logos in derivative patch bundles — these are not relaxed by this skill's MIT license.

## Local reference (not committed)

The `MorpheApp/` directory in this checkout is a local-only reference of the upstream Morphe toolchain repos. It is included in `.gitignore` and will not be committed. Use it to verify doc references like `morphe-patcher/docs/2_2_patch_anatomy.md`.
