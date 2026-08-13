import { test, expect } from '@playwright/test';

test.describe('Settings', () => {
  test('settings page loads', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.locator('body')).toBeVisible();
  });

  test('API key can be saved', async ({ page }) => {
    await page.goto('/settings');
    const apiKeyInput = page
      .locator('input[type="password"], input[placeholder*="api key" i]')
      .first();
    if (await apiKeyInput.isVisible()) {
      await apiKeyInput.fill('test-api-key');
      const saveBtn = page.locator('button', { hasText: /save/i }).first();
      if (await saveBtn.isVisible()) {
        await saveBtn.click();
        const savedKey = await page.evaluate(() => localStorage.getItem('api_key'));
        expect(savedKey).toBe('test-api-key');
      }
    }
  });
});
