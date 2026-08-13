/**
 * Consolidated observability view — A2A traffic and external API calls.
 */

import { A2ATracker } from '../Observability/A2ATracker';
import { ExternalCallsPanel } from '../Observability/ExternalCallsPanel';

export function ObservabilityPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-100">Observability</h1>
        <p className="text-sm text-gray-400 mt-1">
          Agent-to-agent message flow and external service calls
        </p>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="min-h-[24rem]">
          <A2ATracker />
        </div>
        <div className="min-h-[24rem]">
          <ExternalCallsPanel />
        </div>
      </div>
    </div>
  );
}
