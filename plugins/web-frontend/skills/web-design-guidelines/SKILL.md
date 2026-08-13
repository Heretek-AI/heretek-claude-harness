---
name: web-design-guidelines
description: Audit web interfaces against 100+ production accessibility, UX, responsive layout, and focus management rules.
---

# web-design-guidelines

Comprehensive web interface and accessibility audit skill based on Vercel's Web Interface Guidelines.

## Core Audit Checklist

Inspect frontend code against these rules:

1. **Accessibility (WCAG 2.1 AA)**:
   - Every interactive element (`<button>`, `<a>`, `<input>`) must have an explicit accessible name or `aria-label`.
   - Focus rings (`outline-ring`) must be visible for keyboard navigation (`:focus-visible`).
   - Color contrast ratio between text and background must be at least 4.5:1 (3:1 for large text).
   - Images must carry descriptive `alt` text; decorative icons must use `aria-hidden="true"`.
2. **Touch & Interaction Targets**:
   - Minimum touch target size on mobile is `44x44px`.
   - Buttons must provide clear visual states (`hover`, `active`, `disabled`, `loading`).
3. **Layout & Responsiveness**:
   - Containers must adjust fluidly; no fixed pixel widths (`width: 1200px`) causing horizontal scrollbars on mobile.
   - Text inputs must use `font-size: 16px` on mobile to prevent automatic iOS zoom.
4. **Form Handling**:
   - Inputs must link to explicit `<label htmlFor="...">` elements.
   - Form submission errors must announce via `aria-live="polite"` or `role="alert"`.

## Reporting Format

Emit findings as a structured checklist grouped by severity: Blocking (Accessibility/A11y violation) vs Suggestion (UX refinement).
