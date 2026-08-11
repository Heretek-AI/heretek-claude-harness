# Add check-json hook to .pre-commit-config.yaml

The repo has a minimal `.pre-commit-config.yaml` with one existing hook
(`trailing-whitespace`). Add a second local hook that runs `prettier` against
every `.json` file. The new hook must:

- Have id `check-json`
- Use `entry: npx --no-install prettier --write`
- Apply to files matching the regex `\.json$`
- Appear **after** the existing trailing-whitespace hook so the diff is minimal.

Constraints:
- Do not modify any other files.
- Keep the file valid YAML.
