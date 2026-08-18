import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MagnifyingGlassIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { getFileTypes } from '../services/api';
import { FileFilters, SizeUnit } from '../types/file';
import { useDebouncedValue } from '../hooks/useDebouncedValue';

interface FileSearchProps {
  filters: FileFilters;
  onChange: (filters: FileFilters) => void;
}

const SIZE_UNITS: SizeUnit[] = ['B', 'KB', 'MB', 'GB'];

const FileSearch: React.FC<FileSearchProps> = ({ filters, onChange }) => {
  const [searchInput, setSearchInput] = useState(filters.search);
  const debouncedSearch = useDebouncedValue(searchInput, 350);
  const { data: fileTypes } = useQuery({ queryKey: ['fileTypes'], queryFn: getFileTypes });

  useEffect(() => {
    if (debouncedSearch !== filters.search) {
      onChange({ ...filters, search: debouncedSearch });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  const update = <K extends keyof FileFilters>(key: K, value: FileFilters[K]) => {
    onChange({ ...filters, [key]: value });
  };

  const hasActiveFilters = Boolean(
    filters.search ||
      filters.fileType ||
      filters.minSize ||
      filters.maxSize ||
      filters.startDate ||
      filters.endDate
  );

  const clearAll = () => {
    setSearchInput('');
    onChange({
      search: '',
      fileType: '',
      minSize: '',
      minSizeUnit: 'KB',
      maxSize: '',
      maxSizeUnit: 'MB',
      startDate: '',
      endDate: '',
      ordering: filters.ordering,
    });
  };

  return (
    <div className="mb-6 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="relative mb-4">
        <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search files by name..."
          className="w-full rounded-lg border border-gray-300 py-2 pl-10 pr-4 focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-500">File type</label>
          <select
            value={filters.fileType}
            onChange={(e) => update('fileType', e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          >
            <option value="">All types</option>
            {(fileTypes || []).map((type) => (
              <option key={type} value={type}>
                .{type}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-gray-500">Min size</label>
          <div className="flex gap-1">
            <input
              type="number"
              min={0}
              value={filters.minSize}
              onChange={(e) => update('minSize', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
            <select
              value={filters.minSizeUnit}
              onChange={(e) => update('minSizeUnit', e.target.value as SizeUnit)}
              className="rounded-lg border border-gray-300 px-2 text-sm"
            >
              {SIZE_UNITS.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-gray-500">Max size</label>
          <div className="flex gap-1">
            <input
              type="number"
              min={0}
              value={filters.maxSize}
              onChange={(e) => update('maxSize', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
            <select
              value={filters.maxSizeUnit}
              onChange={(e) => update('maxSizeUnit', e.target.value as SizeUnit)}
              className="rounded-lg border border-gray-300 px-2 text-sm"
            >
              {SIZE_UNITS.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-gray-500">Uploaded after</label>
          <input
            type="date"
            value={filters.startDate}
            onChange={(e) => update('startDate', e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-gray-500">Uploaded before</label>
          <input
            type="date"
            value={filters.endDate}
            onChange={(e) => update('endDate', e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
        </div>
      </div>

      {hasActiveFilters && (
        <button
          onClick={clearAll}
          className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700"
        >
          <XMarkIcon className="h-4 w-4" />
          Clear filters
        </button>
      )}
    </div>
  );
};

export default FileSearch;
