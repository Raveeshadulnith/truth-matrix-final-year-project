import type { JsonValue } from '../api/deepfakeApi';

const SENSITIVE_KEY = /(?:gps|latitude|longitude|coordinates?|serial(?:number)?|secret|token|certificate)/i;

export function humanizeForensicLabel(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function redactSensitiveJson(value: JsonValue, key = ''): JsonValue {
  if (SENSITIVE_KEY.test(key)) return '[redacted]';
  if (Array.isArray(value)) {
    return value.map((entry) => redactSensitiveJson(entry));
  }
  if (typeof value === 'object' && value !== null) {
    return Object.fromEntries(
      Object.entries(value).map(([childKey, childValue]) => [
        childKey,
        redactSensitiveJson(childValue, childKey),
      ])
    );
  }
  return value;
}

export function sortJsonValue(value: JsonValue): JsonValue {
  if (Array.isArray(value)) return value.map(sortJsonValue);
  if (typeof value === 'object' && value !== null) {
    return Object.fromEntries(
      Object.keys(value)
        .sort((left, right) => left.localeCompare(right))
        .map((key) => [key, sortJsonValue(value[key])])
    );
  }
  return value;
}
