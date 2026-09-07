import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { FileUpload } from './components/FileUpload';
import FileStats from './components/FileStats';
import FileSearch from './components/FileSearch';
import FileList from './components/FileList';
import { FileFilters } from './types/file';
import AuthPanel from './components/AuthPanel';
import { getAuthTokens, setAuthTokens } from './services/api';

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
  searchMode: 'filename',
};

const App: React.FC = () => {
  const [filters, setFilters] = useState<FileFilters>(DEFAULT_FILTERS);
  const [authenticated, setAuthenticated] = useState(Boolean(getAuthTokens()?.access));

  if (!authenticated) {
    return <AuthPanel onAuthenticated={() => setAuthenticated(true)} />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-gray-50">
        <header className="border-b border-gray-200 bg-white">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-5">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">File Vault System</h1>
              <p className="text-sm text-gray-500">
                Private file references, shared blob storage and meaning-based search.
              </p>
            </div>
            <button
              onClick={() => {
                setAuthTokens(null);
                queryClient.clear();
                setAuthenticated(false);
              }}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
            >
              Sign out
            </button>
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
