import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { FileUpload } from './components/FileUpload';
import FileStats from './components/FileStats';
import FileSearch from './components/FileSearch';
import FileList from './components/FileList';
import { FileFilters } from './types/file';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30,
      refetchOnWindowFocus: false,
    },
  },
});

const DEFAULT_FILTERS: FileFilters = {
  search: '',
  fileType: '',
  minSize: '',
  minSizeUnit: 'KB',
  maxSize: '',
  maxSizeUnit: 'MB',
  startDate: '',
  endDate: '',
  ordering: '-uploaded_at',
};

const App: React.FC = () => {
  const [filters, setFilters] = useState<FileFilters>(DEFAULT_FILTERS);

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-gray-50">
        <header className="border-b border-gray-200 bg-white">
          <div className="mx-auto max-w-5xl px-4 py-5">
            <h1 className="text-2xl font-bold text-gray-900">File Vault System</h1>
            <p className="text-sm text-gray-500">
              Upload, search and manage your files with automatic duplicate detection.
            </p>
          </div>
        </header>

        <main className="mx-auto max-w-5xl px-4 py-6">
          <FileUpload />
          <FileStats />
          <FileSearch filters={filters} onChange={setFilters} />
          <FileList filters={filters} />
        </main>
      </div>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
};

export default App;
