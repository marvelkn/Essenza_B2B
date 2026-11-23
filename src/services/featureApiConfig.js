import AsyncStorage from '@react-native-async-storage/async-storage';
const LOCAL_KEY = '@essenza/b2b-local-feature-api-v1';
const USB_URL = 'http://127.0.0.1:8000';

export function isLocalApiMode() {
  return true;
}

export function defaultFeatureApiUrl() {
  return USB_URL;
}

function isPrivateHost(host) {
  if (['localhost', '127.0.0.1'].includes(host)) { return true; }
  const parts = host.split('.');
  if (parts.length !== 4 || parts.some(part => !/^\d+$/.test(part) || Number(part) > 255)) {
    return false;
  }
  const [a, b] = parts.map(Number);
  return a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168);
}

export function validateFeatureApiUrl(value) {
  const trimmed = value.trim().replace(/\/+$/, '');
  if (!trimmed) { throw new Error('Masukkan alamat layanan analisis.'); }
  let url;
  try { url = new URL(trimmed); } catch { throw new Error('Alamat layanan tidak valid.'); }
  if (url.username || url.password || url.search || url.hash || url.pathname !== '/' ||
      !isPrivateHost(url.hostname) || !['http:', 'https:'].includes(url.protocol)) {
    throw new Error('Gunakan alamat dasar HTTP/HTTPS lokal (localhost/IP jaringan pribadi), tanpa path.');
  }
  return trimmed;
}

export async function loadFeatureApiUrl() {
  // Keep local settings isolated from cloud addresses saved by earlier builds.
  const local = await AsyncStorage.getItem(LOCAL_KEY);
  return validateFeatureApiUrl(local || defaultFeatureApiUrl());
}

export async function saveFeatureApiUrl(value) {
  const url = validateFeatureApiUrl(value);
  await AsyncStorage.setItem(LOCAL_KEY, url);
  return url;
}
