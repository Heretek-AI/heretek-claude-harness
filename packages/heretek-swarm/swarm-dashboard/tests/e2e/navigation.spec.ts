import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test('home page loads', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('body')).toBeVisible();
  });

  test('navigate to agents page', async ({ page }) => {
    await page.goto('/');
    const agentsLink = page.locator('nav a, button', { hasText: /agents/i }).first();
    if (await agentsLink.isVisible()) {
      await agentsLink.click();
      await expect(page).toHaveURL(/\/agents/);
    }
  });

  test('navigate to settings page', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.locator('body')).toBeVisible();
  });

  test('navigate to deliberations page', async ({ page }) => {
    await page.goto('/deliberations');
    await expect(page.locator('body')).toBeVisible();
  });
});
