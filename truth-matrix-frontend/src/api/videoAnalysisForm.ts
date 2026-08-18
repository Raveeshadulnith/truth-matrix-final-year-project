export interface VideoSegmentFields {
  startSeconds: number;
  durationSeconds: number;
}

/** Build a request with the original File and a separate analysis range. */
export function createVideoAnalysisFormData(
  file: File,
  selection?: VideoSegmentFields
): FormData {
  const formData = new FormData();
  formData.append('file', file);

  if (selection) {
    formData.append('segment_start_seconds', selection.startSeconds.toString());
    formData.append(
      'segment_duration_seconds',
      selection.durationSeconds.toString()
    );
  }

  return formData;
}
