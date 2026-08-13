# react-hook-form + zod spike — Phase 2B.4

## Purpose

Validate that **react-hook-form** (https://github.com/react-hook-form/react-hook-form,
MIT, ~42k stars) and **zod** (https://github.com/colinhacks/zod,
MIT, ~33k stars) are the integration target for the 4 large
hand-managed forms and 6+ smaller forms across the dashboard.

## Candidate files for cutover (~2,000 LOC combined)

| File | LOC | Replaced by |
|------|-----|-------------|
| `components/Setup/SetupWizard.tsx` | 1,180 | `useForm` + `zod` schema |
| `components/Settings/ModelGarage.tsx` | 1,270 | `useForm` + `zod` schema |
| `components/Workflow/NodeConfigPanel.tsx` | 784 | `useForm` (dynamic schema) |
| `components/Agents/AgentConfigPanel.tsx` | 290 | `useForm` + `zod` |
| `components/Settings/*Section.tsx` (4 files) | ~1,000 | `useForm` + `zod` |
| `utils/setupValidation.ts` | 541 | `zod` schemas |
| **Total** | **~5,065** | **net ~2,000 after adding deps** |

## Why this matters

The current setup uses **zero form library**; every form is
hand-managed `useState` with ad-hoc validation:

```tsx
const [apiKey, setApiKey] = useState('');
const [endpoint, setEndpoint] = useState('');
const [error, setError] = useState('');

const handleSubmit = () => {
  if (!apiKey) { setError('Required'); return; }
  // ... 30 more lines of manual validation
};
```

This pattern is unmaintainable at scale: each form has its own
state machine, validation is duplicated, dirty tracking is manual,
and there's no type safety. react-hook-form replaces this with
~10 lines per form:

```tsx
const { register, handleSubmit, formState: { errors } } = useForm({
  resolver: zodResolver(schema),
});

return (
  <form onSubmit={handleSubmit(onSubmit)}>
    <input {...register('apiKey')} />
    {errors.apiKey && <span>{errors.apiKey.message}</span>}
  </form>
);
```

## Migration pattern

### Step 1: Install deps
```bash
cd swarm-dashboard
npm install react-hook-form @hookform/resolvers zod
```

### Step 2: Convert one form at a time
For each form, extract its validation rules into a zod schema:

```ts
const setupSchema = z.object({
  apiHost: z.string().url(),
  apiKey: z.string().min(1),
  // ... etc
});

type SetupForm = z.infer<typeof setupSchema>;
```

Then use the schema in the component with `zodResolver`.

### Step 3: Delete `utils/setupValidation.ts`
The hand-rolled URL/API validators are subsumed by zod schemas.

## Kill criteria

- If a form needs custom async validation (e.g. probe the API
  endpoint on submit), use `zod.refine` + react-hook-form's
  `mode: 'onBlur'`.

## Result

- react-hook-form v7+ has zero re-renders on field changes
  (uses uncontrolled inputs).
- zod's type inference eliminates the duplicated schema / type
  pair: define once, infer everywhere.
- Validation errors are consistent across forms (single source
  of truth: the zod schema).

## Migration PR plan

1. Add deps.
2. Migrate `components/Settings/AgentDefaultsSection.tsx` (smallest).
3. Migrate the 3 other Settings sections.
4. Migrate `components/Agents/AgentConfigPanel.tsx`.
5. Migrate `components/Workflow/NodeConfigPanel.tsx` (dynamic schema).
6. Migrate `components/Settings/ModelGarage.tsx` (largest single form).
7. Migrate `components/Setup/SetupWizard.tsx` (5-step wizard).
8. Delete `utils/setupValidation.ts`.

**Net:** ~2,000 LOC reduction + type-safe forms + consistent
validation across the dashboard.
