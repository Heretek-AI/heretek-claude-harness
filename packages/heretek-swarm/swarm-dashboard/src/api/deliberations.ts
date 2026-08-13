// REST client for /api/deliberations.
import { api } from './client';
import type { DeliberationDetail, DeliberationSummary } from '../types/deliberation';

export async function createDeliberation(problem: string): Promise<string> {
  const r = await api.post<{ id: string; status: string }>('/api/deliberations', { problem });
  return r.data.id;
}

export async function getDeliberation(id: string): Promise<DeliberationDetail> {
  const r = await api.get<DeliberationDetail>(`/api/deliberations/${id}`);
  return r.data;
}

export async function listDeliberations(limit = 20): Promise<DeliberationSummary[]> {
  const r = await api.get<{ items: DeliberationSummary[] }>(`/api/deliberations?limit=${limit}`);
  return r.data.items;
}

export async function interject(id: string, text: string): Promise<void> {
  await api.post(`/api/deliberations/${id}/interject`, { text });
}
