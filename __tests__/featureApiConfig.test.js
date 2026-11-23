import AsyncStorage from '@react-native-async-storage/async-storage';
import { defaultFeatureApiUrl, isLocalApiMode, loadFeatureApiUrl, saveFeatureApiUrl, validateFeatureApiUrl } from '../src/services/featureApiConfig';

const originalDev = global.__DEV__;
beforeEach(() => {
  jest.clearAllMocks();
  AsyncStorage.getItem.mockReset().mockResolvedValue(null);
});
afterEach(() => { global.__DEV__ = originalDev; });

test.each([true, false])('uses the USB local API in every build, development=%s', async development => {
  global.__DEV__ = development;
  expect(isLocalApiMode()).toBe(true);
  expect(defaultFeatureApiUrl()).toBe('http://127.0.0.1:8000');
  expect(await loadFeatureApiUrl()).toBe('http://127.0.0.1:8000');
});

test('ignores legacy cloud settings and preserves the existing local-settings namespace', async () => {
  global.__DEV__ = false;
  AsyncStorage.getItem.mockImplementation(async key => key === '@essenza/b2b-feature-api-v2'
    || key === '@essenza/b2b-feature-api-v1' ? 'https://old-cloud.example.com' : null);
  expect(await loadFeatureApiUrl()).toBe('http://127.0.0.1:8000');
  expect(AsyncStorage.getItem).toHaveBeenCalledTimes(1);
  expect(AsyncStorage.getItem).toHaveBeenCalledWith('@essenza/b2b-local-feature-api-v1');
  expect(await saveFeatureApiUrl('http://192.168.1.8:8000/')).toBe('http://192.168.1.8:8000');
  expect(AsyncStorage.setItem).toHaveBeenCalledWith('@essenza/b2b-local-feature-api-v1', 'http://192.168.1.8:8000');
});

test('reloads a previously saved private-network address', async () => {
  AsyncStorage.getItem.mockResolvedValue('http://192.168.1.8:8000');
  expect(await loadFeatureApiUrl()).toBe('http://192.168.1.8:8000');
});

test('rejects a public address stored in the local-settings key instead of silently using it', async () => {
  AsyncStorage.getItem.mockResolvedValue('https://old-cloud.example.com');
  await expect(loadFeatureApiUrl()).rejects.toThrow();
});

test.each([
  'http://127.0.0.1:8000', 'http://localhost:8000', 'http://10.1.2.3:8000',
  'http://172.16.2.3:8000', 'http://172.31.2.3:8000', 'http://192.168.2.3:8000',
  'https://localhost:8000', 'https://192.168.1.8:8000',
])('accepts a local API address %s', url => { expect(validateFeatureApiUrl(url)).toBe(url); });

test.each([
  'http://example.com', 'https://example.com', 'http://172.32.1.1:8000',
  'https://172.32.1.1:8000', 'http://192.169.1.1:8000', 'http://8.8.8.8:8000',
  'https://8.8.8.8:8000', 'http://localhost:8000/predict', 'http://user:pass@localhost:8000',
  'http://localhost:8000?token=secret', 'http://localhost:8000#fragment',
  'ftp://127.0.0.1:8000', 'not a URL', '',
])('rejects a public or malformed API address %s', url => {
  expect(() => validateFeatureApiUrl(url)).toThrow();
});
