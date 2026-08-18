import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowDownTrayIcon,
  DocumentDuplicateIcon,
  DocumentIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { deleteFile, getDownloadUrl, ListFilesParams, listFiles } from '../services/api';
import { FileFilters } from '../types/file';
import { bytesFromUnit, formatBytes, formatDate } from '../utils/format';

interface FileListProps {
  filters: FileFilters;
}

const FileList: React.FC<FileListProps> = ({ filters }) => {
  const [page, setPage] = useState(1);
  const queryClient = useQueryClient();

  const params: ListFilesParams = useMemo(() => {
    const p: ListFilesParams = { page, ordering: filters.ordering };
    if (filters.search) p.search = filters.search;
    if (filters.fileType) p.file_type = filters.fileType;
    if (filters.minSize) p.min_size = bytesFromUnit(Number(filters.minSize), filters.minSizeUnit);
    if (filters.maxSize) p.max_size = bytesFromUnit(Number(filters.maxSize), filters.maxSizeUnit);
    if (filters.startDate) p.start_date = `${filters.startDate}T00:00:00`;
    if (filters.endDate) p.end_date = `${filters.endDate}T23:59:59`;
    return p;
  }, [filters, page]);

  useEffect(() => {
    setPage(1);
  }, [
    filters.search,
    filters.fileType,
    filters.minSize,
    filters.maxSize,
    filters.startDate,
    filters.endDate,
    filters.ordering,
  ]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['files', params],
    queryFn: () => listFiles(params),
    placeholderData: (previous) => previous,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteFile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['files'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    },
  });

  const handleDelete = (id: string, name: string) => {
    if (window.confirm(`Delete "${name}"? This cannot be undone.`)) {
      deleteMutation.mutate(id);
    }
  };

  const pageSize = 12;
  const totalPages = data ? Math.max(1, Math.ceil(data.count / pageSize)) : 1;

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <h2 className="font-semibold text-gray-800">Files {data ? `(${data.count})` : ''}</h2>
      </div>

      {isLoading && <p className="p-6 text-center text-gray-400">Loading files...</p>}
      {isError && (
        <p className="p-6 text-center text-red-500">Couldn&apos;t load files. Is the backend running?</p>
      )}
      {!isLoading && !isError && data?.results.length === 0 && (
        <p className="p-6 text-center text-gray-400">No files match your search yet.</p>
      )}

      <ul className="divide-y divide-gray-100">
        {data?.results.map((file) => (
          <li key={file.id} className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50">
            <div className="flex-shrink-0 rounded-lg bg-gray-100 p-2">
              <DocumentIcon className="h-5 w-5 text-gray-500" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="truncate font-medium text-gray-800">{file.original_filename}</p>
                {file.is_duplicate && (
                  <span className="inline-flex flex-shrink-0 items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                    <DocumentDuplicateIcon className="h-3 w-3" /> duplicate
                  </span>
                )}
                {!file.is_duplicate && file.duplicate_count > 0 && (
                  <span className="flex-shrink-0 rounded-full bg-primary-100 px-2 py-0.5 text-xs font-medium text-primary-700">
                    {file.duplicate_count} {file.duplicate_count === 1 ? 'copy' : 'copies'} referenced
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-400">
                {formatBytes(file.size)} • {file.file_type ? `.${file.file_type}` : 'unknown type'} •{' '}
                {formatDate(file.uploaded_at)}
              </p>
            </div>
            <div className="flex flex-shrink-0 items-center gap-1">
              <a
                href={getDownloadUrl(file.id)}
                className="rounded-lg p-2 text-gray-400 hover:bg-primary-50 hover:text-primary-600"
                title="Download"
              >
                <ArrowDownTrayIcon className="h-5 w-5" />
              </a>
              <button
                onClick={() => handleDelete(file.id, file.original_filename)}
                className="rounded-lg p-2 text-gray-400 hover:bg-red-50 hover:text-red-600"
                title="Delete"
              >
                <TrashIcon className="h-5 w-5" />
              </button>
            </div>
          </li>
        ))}
      </ul>

      {data && data.count > 0 && (
        <div className="flex items-center justify-between border-t border-gray-200 px-4 py-3 text-sm text-gray-500">
          <span>
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              disabled={!data.previous}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="rounded-lg border border-gray-300 px-3 py-1 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Previous
            </button>
            <button
              disabled={!data.next}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-lg border border-gray-300 px-3 py-1 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileList;
