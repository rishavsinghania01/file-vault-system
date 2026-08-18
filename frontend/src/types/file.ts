export interface FileItem {
  id: string;
  file_url: string | null;
  original_filename: string;
  file_type: string;
  content_type: string;
  size: number;
  uploaded_at: string;
  hash: string | null;
  original: string | null;
  is_duplicate: boolean;
  duplicate_count: number;
}

export interface FileStatsData {
  total_files: number;
  unique_files: number;
  duplicate_files: number;
  storage_used_bytes: number;
  storage_saved_bytes: number;
  total_uploaded_bytes: number;
  savings_percentage: number;
}

export type SizeUnit = 'B' | 'KB' | 'MB' | 'GB';

export interface FileFilters {
  search: string;
  fileType: string;
  minSize: string;
  minSizeUnit: SizeUnit;
  maxSize: string;
  maxSizeUnit: SizeUnit;
  startDate: string;
  endDate: string;
  ordering: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface UploadResponse {
  data: FileItem;
  duplicate: boolean;
  message: string;
}
