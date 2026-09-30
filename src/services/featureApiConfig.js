import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = '@essenza/b2b-feature-api-v2';
const LEGACY_KEY = '@essenza/b2b-feature-api-v1';
const DEBUG_URL = 'http://127.0.0.1:8000';
const RELEASE_URL = 'https://essenzafrontend.vercel.app';

export function validateFeatureApiUrl(value) {
  const trimmed = value.trim().replace(/\/+$/, '');
  if (!trimmed) {
    throw new Error('Masukkan alamat API fitur.');
  }
  let url;
  try {
    url = new URL(trimmed);
  } catch {
    throw new Error('Alamat API tidak valid.');
  }
  const local = ['localhost', '127.0.0.1'].includes(url.hostname);
  if (url.username || url.password || url.search || url.hash || url.pathname !== '/' ||
      (url.protocol !== 'https:' && !(local && url.protocol === 'http:'))) {
    throw new Error('Gunakan alamat dasar HTTPS tanpa path; HTTP hanya untuk localhost.');
  }
  return trimmed;
}

export async function loadFeatureApiUrl() {
  const stored = await AsyncStorage.getItem(KEY);
  if (stored) {
    return validateFeatureApiUrl(stored);
  }
  const legacy = await AsyncStorage.getItem(LEGACY_KEY);
  if (legacy) {
    const url = validateFeatureApiUrl(legacy);
    if (__DEV__ || url !== DEBUG_URL) {
      return url;
    }
  }
  return __DEV__ ? DEBUG_URL : RELEASE_URL;
}

export async function saveFeatureApiUrl(value) {
  const url = validateFeatureApiUrl(value);
  await AsyncStorage.setItem(KEY, url);
  return url;
}
