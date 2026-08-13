import { test, expect } from '@playwright/test';

test('dashboard renders deliberation page', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText(/New Deliberation/i)).toBeVisible();

  await page.locator('textarea').fill('Should we deploy on Friday?');
  await page.getByRole('button', { name: /Start/i }).click();

  // Wait for the deliberation view.
  await expect(page.getByText(/Steward|STEWARD/)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/ALPHA/)).toBeVisible();
  await expect(page.getByText(/BETA/)).toBeVisible();
  await expect(page.getByText(/CHARLIE/)).toBeVisible();

  // Wait for the verdict card to appear (or up to 60s).
  await expect(page.getByText(/FINAL VERDICT/i)).toBeVisible({ timeout: 60_000 });
});
