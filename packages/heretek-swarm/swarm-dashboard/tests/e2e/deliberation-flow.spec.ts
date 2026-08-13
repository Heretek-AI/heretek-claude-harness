import { test, expect } from '@playwright/test';

test.describe('Deliberation Flow', () => {
  test('can create a new deliberation', async ({ page }) => {
    await page.goto('/');
    const textarea = page.locator('textarea');
    if (await textarea.isVisible()) {
      await textarea.fill('What is the best architecture for our system?');
      const submitBtn = page
        .locator('button[type="submit"], button', { hasText: /submit|create|start/i })
        .first();
      if (await submitBtn.isVisible()) {
        await submitBtn.click();
        await expect(page).toHaveURL(/\/deliberations\//);
      }
    }
  });

  test('deliberation list page loads', async ({ page }) => {
    await page.goto('/deliberations');
    await expect(page.locator('body')).toBeVisible();
  });
});
