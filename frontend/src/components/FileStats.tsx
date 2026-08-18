import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ArchiveBoxIcon,
  CircleStackIcon,
  DocumentDuplicateIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { getStats } from '../services/api';
import { formatBytes } from '../utils/format';

const FileStats: React.FC = () => {
  const { data, isLoading } = useQuery({ queryKey: ['stats'], queryFn: getStats });

  const cards: { label: string; value: string; icon: React.ComponentType<{ className?: string }> }[] = [
    {
      label: 'Total Uploads',
      value: data ? data.total_files.toLocaleString() : '-',
      icon: ArchiveBoxIcon,
    },
    {
      label: 'Duplicates Detected',
      value: data ? data.duplicate_files.toLocaleString() : '-',
      icon: DocumentDuplicateIcon,
    },
    {
      label: 'Storage Used',
      value: data ? formatBytes(data.storage_used_bytes) : '-',
      icon: CircleStackIcon,
    },
    {
      label: 'Storage Saved',
      value: data ? `${formatBytes(data.storage_saved_bytes)} (${data.savings_percentage}%)` : '-',
      icon: SparklesIcon,
    },
  ];

  return (
    <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map(({ label, value, icon: Icon }) => (
        <div
          key={label}
          className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
        >
          <div className="rounded-lg bg-primary-50 p-3">
            <Icon className="h-6 w-6 text-primary-600" />
          </div>
          <div className="min-w-0">
            <p className="text-sm text-gray-500">{label}</p>
            <p className={`truncate text-xl font-semibold text-gray-800 ${isLoading ? 'animate-pulse' : ''}`}>
              {value}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
};

export default FileStats;
