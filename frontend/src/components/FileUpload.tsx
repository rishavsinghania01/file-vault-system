import React, { useCallback, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  ArrowUpTrayIcon,
  CheckCircleIcon,
  DocumentDuplicateIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { uploadFile } from '../services/api';

interface FileUploadProps {
  onUploadSuccess?: () => void;
}

interface UploadItem {
  id: string;
  name: string;
  progress: number;
  status: 'uploading' | 'done' | 'duplicate' | 'error';
  message?: string;
}

let uploadCounter = 0;

export const FileUpload: React.FC<FileUploadProps> = ({ onUploadSuccess }) => {
  const [items, setItems] = useState<UploadItem[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const updateItem = (id: string, patch: Partial<UploadItem>) => {
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...patch } : it)));
  };

  const uploadOne = useCallback(
    async (file: File) => {
      const id = `${Date.now()}-${uploadCounter++}`;
      const newItem: UploadItem = { id, name: file.name, progress: 0, status: 'uploading' };
      setItems((prev) => [newItem, ...prev].slice(0, 10));
      try {
        const result = await uploadFile(file, (progress) => updateItem(id, { progress }));
        updateItem(id, {
          progress: 100,
          status: result.duplicate ? 'duplicate' : 'done',
          message: result.message,
        });
        queryClient.invalidateQueries({ queryKey: ['files'] });
        queryClient.invalidateQueries({ queryKey: ['stats'] });
        queryClient.invalidateQueries({ queryKey: ['fileTypes'] });
        onUploadSuccess?.();
      } catch (err) {
        const message =
          (err as { response?: { data?: { error?: string } } })?.response?.data?.error ||
          'Upload failed. Please try again.';
        updateItem(id, { status: 'error', message });
      }
    },
    [onUploadSuccess, queryClient]
  );

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      if (!fileList) return;
      Array.from(fileList).forEach((file) => {
        void uploadOne(file);
      });
    },
    [uploadOne]
  );

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-10 text-center cursor-pointer transition-colors ${
          isDragging ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-primary-400'
        }`}
      >
        <ArrowUpTrayIcon className="h-10 w-10 text-primary-500" />
        <p className="text-gray-700 font-medium">Drag & drop files here, or click to browse</p>
        <p className="text-sm text-gray-400">
          Duplicate content is detected automatically and won&apos;t be stored twice
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = '';
          }}
        />
      </div>

      {items.length > 0 && (
        <ul className="mt-4 space-y-2">
          {items.map((item) => (
            <li key={item.id} className="flex items-center gap-3 rounded-lg bg-gray-50 px-3 py-2 text-sm">
              {item.status === 'uploading' && (
                <div className="h-4 w-4 flex-shrink-0 animate-spin rounded-full border-2 border-primary-300 border-t-primary-600" />
              )}
              {item.status === 'done' && (
                <CheckCircleIcon className="h-5 w-5 flex-shrink-0 text-green-500" />
              )}
              {item.status === 'duplicate' && (
                <DocumentDuplicateIcon className="h-5 w-5 flex-shrink-0 text-amber-500" />
              )}
              {item.status === 'error' && (
                <ExclamationTriangleIcon className="h-5 w-5 flex-shrink-0 text-red-500" />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-gray-800">{item.name}</p>
                {item.status === 'uploading' ? (
                  <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
                    <div
                      className="h-full bg-primary-500 transition-all"
                      style={{ width: `${item.progress}%` }}
                    />
                  </div>
                ) : (
                  <p className={`truncate ${item.status === 'error' ? 'text-red-500' : 'text-gray-500'}`}>
                    {item.message}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
