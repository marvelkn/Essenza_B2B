import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  loadFeatureApiUrl,
  saveFeatureApiUrl,
  validateFeatureApiUrl,
} from '../src/services/featureApiConfig';

test('accepts an HTTPS API and persists it independently from lab history', async () => {
  AsyncStorage.setItem.mockResolvedValue(undefined);
  AsyncStorage.getItem.mockResolvedValueOnce(null).mockResolvedValueOnce(null)
    .mockResolvedValueOnce('https://api.example.com');
  expect(await saveFeatureApiUrl('https://api.example.com/')).toBe('https://api.example.com');
  expect(AsyncStorage.setItem).toHaveBeenCalledWith(
    '@essenza/b2b-feature-api-v2', 'https://api.example.com');
  expect(await loadFeatureApiUrl()).toBe('http://127.0.0.1:8000');
  expect(await loadFeatureApiUrl()).toBe('https://api.example.com');
});

test('release uses the public API instead of a saved debug localhost URL', async () => {
  const wasDev = global.__DEV__;
  global.__DEV__ = false;
  try {
    AsyncStorage.getItem.mockResolvedValueOnce(null).mockResolvedValueOnce(null)
      .mockResolvedValueOnce(null).mockResolvedValueOnce('http://127.0.0.1:8000');
    expect(await loadFeatureApiUrl()).toBe('https://essenzafrontend.vercel.app');
    expect(await loadFeatureApiUrl()).toBe('https://essenzafrontend.vercel.app');
  } finally {
    global.__DEV__ = wasDev;
  }
});

test('rejects HTTP remote URLs and unexpected API paths', () => {
  expect(() => validateFeatureApiUrl('http://example.com')).toThrow();
  expect(() => validateFeatureApiUrl('https://example.com/fingerprint')).toThrow();
  expect(() => validateFeatureApiUrl('https://user:pass@example.com')).toThrow();
});
