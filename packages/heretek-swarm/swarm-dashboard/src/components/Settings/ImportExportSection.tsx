/**
 * Import/Export Section
 *
 * Component for exporting and importing configurations.
 * Allows users to backup and restore system configurations.
 */

import React, { useState, useCallback, useRef } from 'react';
import { useToast } from '../UI/Toast';
import configurationApi from '../../api/configuration';

interface ImportExportSectionProps {
  onImportExport?: () => void;
}

export function ImportExportSection({ onImportExport }: ImportExportSectionProps) {
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importOptions, setImportOptions] = useState({
    overwrite_existing: false,
    skip_conflicts: true,
    import_user_configs: true,
    import_llm_providers: true,
    import_embedding_providers: true,
    import_agent_configs: true,
  });
  const fileInputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();

  const handleExport = useCallback(async () => {
    try {
      setExporting(true);
      const data = await configurationApi.exportConfigurations();

      // Create downloadable file
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `heretek-config-export-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      toast.success('Export successful', 'Configuration exported to file');
      onImportExport?.();
    } catch (error: any) {
      toast.error('Export failed', error.message || 'Could not export configurations');
    } finally {
      setExporting(false);
    }
  }, [toast, onImportExport]);

  const handleImportFile = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setImporting(true);

      // Read and parse file
      const text = await file.text();
      const importData = JSON.parse(text);

      // Validate basic structure
      if (!importData.version) {
        throw new Error('Invalid configuration file format');
      }

      // Import configurations
      const result = await configurationApi.importConfigurations(importData, importOptions) as Record<string, unknown>;

      const totalImported = Object.values((result.imported_count as Record<string, unknown>) || {}).reduce((a, b) => Number(a) + Number(b), 0);
      const totalSkipped = Object.values((result.skipped_count as Record<string, unknown>) || {}).reduce((a, b) => Number(a) + Number(b), 0);
      const totalErrors = Object.values((result.error_count as Record<string, unknown>) || {}).reduce((a, b) => Number(a) + Number(b), 0);

      if (result.success) {
        toast.success(
          'Import successful',
          `Imported ${totalImported} items, skipped ${totalSkipped}`
        );
        onImportExport?.();
      } else {
        toast.warning(
          'Import completed with errors',
          `${totalImported} imported, ${totalErrors} failed`
        );
      }

      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error: any) {
      toast.error('Import failed', error.message || 'Could not import configurations');
    } finally {
      setImporting(false);
    }
  }, [toast, importOptions, onImportExport]);

  const triggerFileSelect = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-white">Import / Export</h2>
        <p className="text-sm text-gray-400 mt-1">
          Backup and restore system configurations
        </p>
      </div>

      {/* Export Section */}
      <div className="bg-gray-900/50 border border-gray-700 rounded-xl p-6">
        <h3 className="text-md font-semibold text-white mb-2">Export Configurations</h3>
        <p className="text-sm text-gray-400 mb-4">
          Download all system configurations as a JSON file for backup or migration.
        </p>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {exporting ? 'Exporting...' : 'Export Configurations'}
        </button>
      </div>

      {/* Import Section */}
      <div className="bg-gray-900/50 border border-gray-700 rounded-xl p-6">
        <h3 className="text-md font-semibold text-white mb-2">Import Configurations</h3>
        <p className="text-sm text-gray-400 mb-4">
          Restore configurations from a previously exported JSON file.
        </p>

        {/* Import Options */}
        <div className="mb-4 space-y-3">
          <h4 className="text-sm font-medium text-gray-300">Import Options</h4>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={importOptions.skip_conflicts}
              onChange={(e) => setImportOptions(prev => ({ ...prev, skip_conflicts: e.target.checked }))}
              className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-400">Skip conflicting items (don't overwrite)</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={importOptions.overwrite_existing}
              onChange={(e) => setImportOptions(prev => ({ ...prev, overwrite_existing: e.target.checked }))}
              className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-400">Overwrite existing configurations</span>
          </label>
        </div>

        {/* What to Import */}
        <div className="mb-4 space-y-2">
          <h4 className="text-sm font-medium text-gray-300">Import Types</h4>

          <div className="grid grid-cols-2 gap-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={importOptions.import_user_configs}
                onChange={(e) => setImportOptions(prev => ({ ...prev, import_user_configs: e.target.checked }))}
                className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-400">System Configs</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={importOptions.import_llm_providers}
                onChange={(e) => setImportOptions(prev => ({ ...prev, import_llm_providers: e.target.checked }))}
                className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-400">LLM Providers</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={importOptions.import_embedding_providers}
                onChange={(e) => setImportOptions(prev => ({ ...prev, import_embedding_providers: e.target.checked }))}
                className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-400">Embedding Providers</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={importOptions.import_agent_configs}
                onChange={(e) => setImportOptions(prev => ({ ...prev, import_agent_configs: e.target.checked }))}
                className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-400">Agent Configs</span>
            </label>
          </div>
        </div>

        {/* File Input */}
        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleImportFile}
            className="hidden"
          />
          <button
            onClick={triggerFileSelect}
            disabled={importing}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {importing ? 'Importing...' : 'Select File'}
          </button>
          <span className="text-xs text-gray-500">
            Choose a JSON configuration file to import
          </span>
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <span className="text-yellow-400 text-lg">⚠️</span>
          <div>
            <h4 className="text-sm font-medium text-yellow-400 mb-1">
              Import Warning
            </h4>
            <p className="text-xs text-gray-400">
              Importing configurations may overwrite existing settings. Make sure to export
              your current configuration before importing. API keys will be imported as-is,
              so ensure your export file is kept secure.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ImportExportSection;
