export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
}

export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 60) return 'Just now';
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
  if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}d ago`;

  return formatDate(dateString);
}

export function formatConfidence(confidence: number): string {
  return `${confidence.toFixed(1)}%`;
}

export function formatProcessingTime(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  return `${seconds.toFixed(1)}s`;
}

export function truncateFilename(
filename: string,
maxLength: number = 30)
: string {
  if (filename.length <= maxLength) return filename;

  const ext = filename.split('.').pop() || '';
  const name = filename.slice(0, filename.length - ext.length - 1);
  const truncatedName = name.slice(0, maxLength - ext.length - 4) + '...';

  return `${truncatedName}.${ext}`;
}

export function getFileTypeIcon(fileType: string): string {
  if (fileType.startsWith('image')) return 'Image';
  if (fileType.startsWith('video')) return 'Video';
  if (fileType.startsWith('audio')) return 'Music';
  return 'File';
}

export function generateShareUrl(shareToken: string): string {
  return `${window.location.origin}/share/${shareToken}`;
}

export function classNames(
...classes: (string | boolean | undefined | null)[])
: string {
  return classes.filter(Boolean).join(' ');
}